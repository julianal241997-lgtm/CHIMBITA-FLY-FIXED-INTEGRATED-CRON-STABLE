#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CHIMBITA-FLY-WEB-FIXED-INTEGRATED — Silent, token auto-check, full scan, fallback, watchdog 6h
import json, time, traceback, requests, numpy as np

WATCHDOG_SECONDS = 6 * 60 * 60
START_TS = time.time()
def watchdog_ok(): return (time.time() - START_TS) < WATCHDOG_SECONDS

TELEGRAM_TOKEN = "8364292253:AAE7zlGjDqGV63_0DuILVVJZCFb91igxA8Y"
CHAT_ID = "1982879600"
TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def tg_send(text):
    try: requests.post(f"{TG_API}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=20)
    except Exception: pass
def tg_send_file(b, filename, caption):
    try: requests.post(f"{TG_API}/sendDocument", data={"chat_id": CHAT_ID, "caption": caption}, files={"document": (filename, b, "application/json")}, timeout=30)
    except Exception: pass
def telegram_token_check():
    try:
        r=requests.get(f"{TG_API}/getMe",timeout=15)
        if r.status_code!=200 or not r.json().get("ok",False):
            tg_send("🚨 Telegram connection failed.")
            return False
        return True
    except Exception:
        tg_send("🚨 Telegram connection failed (network)."); return False

FALLBACK_ENDPOINTS=["https://api4.binance.com","https://api1.binance.com","https://api2.binance.com","https://api3.binance.com","https://api.binance.com"]
TIMEFRAMES=["1h","2h","4h","1d"]; CANDLE_LIMIT=300

def ema(a,p):
    a=np.asarray(a,dtype=float); 
    if len(a)<p: return np.array([])
    alpha=2.0/(p+1.0); out=np.empty_like(a,dtype=float); out[0]=a[0]
    for i in range(1,len(a)): out[i]=alpha*a[i]+(1-alpha)*out[i-1]
    return out
def rsi(c,period=14):
    c=np.asarray(c,dtype=float); 
    if len(c)<=period: return np.array([])
    d=np.diff(c); up=np.where(d>0,d,0.0); dn=np.where(d<0,-d,0.0)
    up_e=ema(up,period); dn_e=ema(dn,period); rs=np.divide(up_e,dn_e,out=np.zeros_like(up_e),where=dn_e!=0)
    r=100.0-(100.0/(1.0+rs)); pad=len(c)-len(r); return np.concatenate([np.full(pad,np.nan),r])
def macd(c,fast=12,slow=26,signal=9):
    c=np.asarray(c,dtype=float); 
    if len(c)<slow+signal+2: return np.array([]),np.array([]),np.array([])
    e1=ema(c,fast); e2=ema(c,slow); L=min(len(e1),len(e2)); dif=e1[-L:]-e2[-L:]; dea=ema(dif,signal)
    L2=min(len(dif),len(dea)); dif,dea=dif[-L2:],dea[-L2:]; return dif,dea,dif-dea
def bbands(c,period=20,m=2.0):
    c=np.asarray(c,dtype=float); 
    if len(c)<period: return np.array([]),np.array([]),np.array([])
    ma=np.convolve(c,np.ones(period)/period,mode="valid"); std=np.array([np.std(c[i-period:i]) for i in range(period,len(c)+0)])
    return ma-m*std, ma, ma+m*std
def crossover(a,b): return len(a)>=2 and len(b)>=2 and a[-2]<=b[-2] and a[-1]>b[-1]
def golden_cross(c): return crossover(ema(c,50), ema(c,200))
def ema_ribbon_flip(c): return crossover(ema(c,8), ema(c,21))
def bb_squeeze(c,period=20,m=2.0,th=0.03):
    lo,mid,up=bbands(c,period,m); 
    if len(up)==0: return False
    w=(up[-1]-lo[-1])/(mid[-1] if mid[-1]!=0 else 1.0); return w<th
def volume_spike(v,f=2.0):
    v=np.asarray(v,dtype=float); 
    if len(v)<30: return False
    base=np.median(v[-30:-2]) if len(v)>32 else np.median(v[:-2]); return v[-1]>f*base
def bullish_div(lows,ind):
    if len(lows)<6 or len(ind)<6: return False
    return (np.min(lows[-3:])<np.min(lows[-6:-3])) and (np.nanmin(ind[-3:])>np.nanmin(ind[-6:-3]))

import ccxt
def build_exchange(host):
    ex=ccxt.binanceusdm({"enableRateLimit":True,"timeout":20000})
    try: ex.urls["api"]=host; ex.urls["fapi"]=host
    except Exception: pass
    return ex
def load_usdt_perps(ex):
    mk=ex.load_markets(); out=[]
    for s,m in mk.items():
        try:
            if m.get('swap',False) and m.get('linear',True) and m.get('quote','')=='USDT':
                if str(m.get('info',{}).get('contractType','')).upper()=='PERPETUAL': out.append(s)
        except Exception: continue
    return sorted(set(out))
def fetch_ohlcv(ex,sym,tf,limit):
    for _ in range(2):
        try: return ex.fetch_ohlcv(sym,timeframe=tf,limit=limit) or []
        except Exception: time.sleep(0.25)
    return []
def eval_symbol_tf(ex,sym,tf):
    if not watchdog_ok(): return None
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
    if not telegram_token_check(): return 2
    tg_send("🔵 Bot CHIMBITA-FLY-FIXED-INTEGRATED started on Fly.io")
    ep,meta=pick_endpoint()
    if not ep:
        tg_send("🚨 All Binance endpoints unavailable; will retry on next run.")
        if meta:
            try: tg_send_file(json.dumps({"last_error":meta},indent=2).encode("utf-8"),"exchangeInfo_error.json","exchangeInfo_error.json (debug)")
            except Exception: pass
        return 2
    if ep!=FALLBACK_ENDPOINTS[0]: tg_send(f"⚠️ Endpoint issue detected — switched to backup node: {ep}")
    ex=build_exchange(ep)
    try: syms=load_usdt_perps(ex)
    except Exception as e: tg_send(f"🚨 Could not load markets: {e}"); return 2
    syms=syms[:600]; alerts=[]
    for s in syms:
        for tf in TIMEFRAMES:
            res=eval_symbol_tf(ex,s,tf)
            if res: alerts.append(res)
    if alerts: tg_send("✅ Signals (3+ criteria):\n"+ "\n".join(alerts[:60]))
    else: tg_send(f"✅ Scan completed — analyzed {len(syms)} pairs. No aligned signals found.")
    return 0
if __name__=="__main__":
    try:
        code=run()
        if not watchdog_ok(): raise SystemExit(0)
        raise SystemExit(code)
    except Exception as e:
        try: tg_send(f"❌ Fatal error: {e}")
        except Exception: pass
        raise
