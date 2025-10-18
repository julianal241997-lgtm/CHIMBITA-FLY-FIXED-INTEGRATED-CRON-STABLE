CHIMBITA-FLY-WEB-FIXED-INTEGRATED
=================================
Despliegue directo desde el panel WEB de Fly.io. Incluye:
- Verificación de token de Telegram en el arranque.
- Fallback de endpoints Binance.
- Watchdog silencioso (6h) por si el proceso se queda colgado.
- Ejecución una vez y finaliza (cron-friendly).

Pasos WEB
---------
1) Sube este ZIP a un repositorio en GitHub.
2) En Fly.io → "Launch from GitHub" → selecciona ese repo.
3) Región 'scl' y nombre de app 'chimbita-fly-web'.
4) Deploy.

Cron (cada hora)
----------------
1) fly images list -a chimbita-fly-web
2) fly machines create -a chimbita-fly-web --region scl \
     --schedule "0 * * * *" \
     --image registry.fly.io/chimbita-fly-web:deployment-<HASH> \
     --command "python scan_bot.py"

Prueba manual
-------------
fly ssh console -a chimbita-fly-web -C "python scan_bot.py"

Actualizar
----------
fly deploy -a chimbita-fly-web

Eliminar
--------
fly apps destroy chimbita-fly-web
