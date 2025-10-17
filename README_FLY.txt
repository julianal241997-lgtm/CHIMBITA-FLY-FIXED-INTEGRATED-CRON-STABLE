CHIMBITA-FLY-FIXED-INTEGRATED-CRON-STABLE-RESILIENT
===================================================
Bot Telegram (Binance USDT perpetuals) — ejecución cada hora con Fly Machines (cron) y
una ejecución inmediata tras el deploy. Silencioso (sin prints); notifica por Telegram.

Despliegue (CLI)
----------------
1) fly auth login
2) Descomprime y entra al directorio del proyecto.
3) fly launch --name chimbita-fly-fixed --region scl --no-deploy
4) fly deploy

Prueba manual
-------------
fly ssh console -a chimbita-fly-fixed -C "python scan_bot.py"

Programar cron cada hora
------------------------
1) Obtén la imagen del último deploy:
   fly images list -a chimbita-fly-fixed

2) Crea la Machine con schedule (cada hora):
   fly machines create -a chimbita-fly-fixed --region scl      --schedule "0 * * * *"      --image registry.fly.io/chimbita-fly-fixed:deployment-<HASH>      --command "python scan_bot.py"

Actualizar
----------
fly deploy -a chimbita-fly-fixed

Eliminar
--------
fly apps destroy chimbita-fly-fixed

Notas
-----
- El bot envía a Telegram: inicio, fallback de endpoint, fin de escaneo y errores.
- Fallback automático de endpoints Binance (api4 → api1 → api2 → api3 → api).
- Sin variables de entorno: token/chat_id integrados.
