#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CHIMBITA-FLY-FIXED-INTEGRATED (cron, stable, resilient) — silent (Telegram only)
import json, time, traceback, requests, numpy as np

TELEGRAM_TOKEN = "8364292253:AAE7zlGjDqGV63_0DuILVVJZCFb91igxA8Y"
CHAT_ID = "1982879600"
TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def tg_send(text):
    try:
        requests.post(f"{TG_API}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=20)
    except Exception:
        pass

def tg_send_file(bytes_content: bytes, filename: str, caption: str):
    try:
        requests.post(f"{TG_API}/sendDocument",
                      data={"chat_id": CHAT_ID, "caption": caption},
                      files={"document": (filename, bytes_content, "application/json")},
                      timeout=30)
    except Exception:
        pass

FALLBACK_ENDPOINTS = [
    "https://api4.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api.binance.com",
]

TIMEFRAMES = ["1h","2h","4h","1d"]
CANDLE_LIMIT = 300

def ema(arr, period):
    arr = np.asarray(arr, dtype=float)
    if len(arr) < period: return np.array([])
    alpha = 2.0/(period+1.0)
    out = np.empty_like(arr, dtype=float); out[0]=arr[0]
    for i in range(1,len(arr)): out[i]=alpha*arr[i]+(1-alpha)*out[i-1]
    return out

def rsi(closes, period=14):
    closes = np.asarray(closes, dtype=float)
    if len(closes) <= period: return np.array([])
    deltas = np.diff(closes)
    up = np.where(deltas>0, deltas, 0.0); down = np.where(deltas<0, -deltas, 0.0)
    up_e = ema(up, period); down_e = ema(down, period)
    rs = np.divide(up_e, down_e, out=np.zeros_like(up_e), where=down_e!=0)
    r = 100.0 - (100.0/(1.0+rs))
    pad = len(closes)-len(r); return np.concatenate([np.full(pad, np.nan), r])

def macd(closes, fast=12, slow=26, signal=9):
    closes = np.asarray(closes, dtype=float)
    if len(closes) < slow+signal+2: return np.array([]),np.array([]),np.array([])
    e1 = ema(closes, fast); e2 = ema(closes, slow)
    L=min(len(e1),len(e2)); dif=e1[-L:]-e2[-L:]; dea=ema(dif, signal)
    L2=min(len(dif),len(dea)); dif,dea=dif[-L2:],dea[-L2:]; return dif,dea,dif-dea

def bbands(closes, period=20, mult=2.0):
    closes = np.asarray(closes, dtype=float)
    if len(closes) < period: return np.array([]),np.array([]),np.array([])
    ma = np.convolve(closes, np.ones(period)/period, mode="valid")
    std = np.array([np.std(closes[i-period:i]) for i in range(period,len(closes)+0)])
    return ma-mult*std, ma, ma+mult*std

def crossover(a,b): return len(a)>=2 and len(b)>=2 and a[-2]<=b[-2] and a[-1]>b[-1]
def golden_cross(c): return crossover(ema(c,50), ema(c,200))
def ema_ribbon_flip(c): return crossover(ema(c,8), ema(c,21))
def bb_squeeze(c, period=20, mult=2.0, th=0.03):
    lo,mid,up=bbands(c,period,mult); 
    if len(up)==0: return False
    w=(up[-1]-lo[-1])/(mid[-1] if mid[-1]!=0 else 1.0); return w<th
def volume_spike(v, factor=2.0):
    v=np.asarray(v,dtype=float); 
    if len(v)<30: return False
    base=np.median(v[-30:-2]) if len(v)>32 else np.median(v[:-2]); return v[-1]>factor*base
def bullish_div(lows, ind):
    if len(lows)<6 or len(ind)<6: return False
    return (np.min(lows[-3:])<np.min(lows[-6:-3])) and (np.nanmin(ind[-3:])>np.nanmin(ind[-6:-3]))

import ccxt

def build_exchange(host):
    ex=ccxt.binanceusdm({"enableRateLimit":True,"timeout":20000})
    try:
        ex.urls["api"]=host; ex.urls["fapi"]=host
    except Exception: pass
    return ex

def load_usdt_perps(ex):
    mk=ex.load_markets(); out=[]
    for s,m in mk.items():
        try:
            if m.get('swap',False) and m.get('linear',True) and m.get('quote','')=='USDT':
                if str(m.get('info',{}).get('contractType','')).upper()=='PERPETUAL':
                    out.append(s)
        except Exception: continue
    return sorted(set(out))

def fetch_ohlcv(ex,sym,tf,limit):
    for _ in range(2):
        try: return ex.fetch_ohlcv(sym, timeframe=tf, limit=limit) or []
        except Exception: time.sleep(0.2)
    return []

def eval_symbol_tf(ex,sym,tf):
    o=fetch_ohlcv(ex,sym,tf,CANDLE_LIMIT)
    if len(o)<210: return None
    closes=[c[4] for c in o]; lows=[c[3] for c in o]; vols=[c[5] if len(c)>5 else 0 for c in o]
    score=0; det=[]
    if golden_cross(closes): score+=1; det.append("Golden Cross")
    r=rsi(closes,14); dif,dea,h=macd(closes)
    if bullish_div(lows,r): score+=1; det.append("RSI Bull Div")
    if len(h)>0 and bullish_div(lows,h): score+=1; det.append("MACD Bull Div")
    if bb_squeeze(closes): score+=1; det.append("BB Squeeze")
    if ema_ribbon_flip(closes): score+=1; det.append("EMA 8/21 Flip")
    if volume_spike(vols): score+=1; det.append("Volume Spike")
    if score>=3:
        label="HIGH" if score>=5 else ("MEDIUM" if score==4 else "LOW")
        return f"• {sym} [{tf.upper()}] — {label} ({score}/5) — {', '.join(det)}"
    return None

def pick_endpoint():
    last=None
    for ep in FALLBACK_ENDPOINTS:
        try:
            r=requests.get(ep.rstrip('/')+'/fapi/v1/exchangeInfo',timeout=12)
            if r.status_code==200 and 'symbols' in r.json(): return ep,None
            else: last={"endpoint":ep,"status":r.status_code,"body":r.text[:300]}
        except Exception as e:
            last={"endpoint":ep,"error":str(e)}
    return "",last

def run():
    tg_send("🔵 Bot CHIMBITA-FLY-FIXED-INTEGRATED started on Fly.io")
    ep,meta=pick_endpoint()
    if not ep:
        tg_send("🚨 Critical bot error: all Binance endpoints blocked/unavailable in current region.")
        if meta:
            try:
                blob=json.dumps({"last_error":meta},indent=2).encode("utf-8")
                tg_send_file(blob,"exchangeInfo_error.json","exchangeInfo_error.json (debug)")
            except Exception: pass
        return 2
    if ep!=FALLBACK_ENDPOINTS[0]:
        tg_send(f"⚠️ Endpoint issue detected — fallback activated. Using: {ep}")
    ex=build_exchange(ep)
    try:
        syms=load_usdt_perps(ex)
    except Exception as e:
        tg_send(f"🚨 Could not load markets: {e}"); return 2
    syms=syms[:600]
    alerts=[]
    for s in syms:
        for tf in TIMEFRAMES:
            try:
                r=eval_symbol_tf(ex,s,tf)
                if r: alerts.append(r)
            except Exception: continue
    if alerts:
        tg_send("✅ Signals (3+ criteria):\n"+ "\n".join(alerts[:60]))
    else:
        tg_send(f"✅ Scan completed — analyzed {len(syms)} pairs. No aligned signals found.")
    return 0

if __name__=="__main__":
    try: raise SystemExit(run())
    except Exception as e:
        try: tg_send(f"❌ Fatal error: {e}")
        except Exception: pass
        raise
