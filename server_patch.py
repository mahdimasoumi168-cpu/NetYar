"""Runtime hardening for Rubika webhook/button handling."""
import asyncio, json, time, hashlib, logging
log=logging.getLogger('netyar.server_patch')

def install():
 import server
 if getattr(server,'_netyar_server_patch_installed',False): return
 def rb_text(update):
  u=server._rubika_inner(update); m=server._rubika_message(u)
  a=m.get('aux_data') if isinstance(m,dict) else None
  if isinstance(a,str):
   try: a=json.loads(a)
   except Exception: a=None
  # Rubika callback/button events carry the stable button id in aux_data.
  # Prefer it over stale visible text so old keyboards remain functional.
  if isinstance(a,dict):
   for k in ('button_id','button_text','text'):
    if a.get(k): return str(a[k]).strip()
  if isinstance(m,dict):
   for k in ('button_id','button_text','text'):
    if m.get(k): return str(m[k]).strip()
  return ''
 server._rubika_text=rb_text
 async def watchdog():
  while True:
   try:
    await asyncio.sleep(90)
    if server.telegram_app is not None:
     try:
      info=await server.telegram_app.bot.get_webhook_info(); expected=server.public_url('/telegram/update'); actual=(info.url or '').rstrip('/')
      if actual != expected.rstrip('/'):
       secret=server.os.getenv('TELEGRAM_WEBHOOK_SECRET','').strip() or None
       await server.telegram_app.bot.set_webhook(url=expected,allowed_updates=None,secret_token=secret)
      server.telegram_ready=True
     except Exception:
      server.telegram_ready=False; log.exception('Telegram watchdog check failed')
    try:
     import rubika_v2 as rb
     info=rb.call('getMe')
     server.rubika_ready=bool(isinstance(info,dict) and ((info.get('bot') or {}).get('bot_id') or info.get('bot_id')))
    except Exception:
     server.rubika_ready=False; log.exception('Rubika health check failed')
   except asyncio.CancelledError: return
   except Exception: log.exception('watchdog failed')
 server._integration_watchdog=watchdog
 server._netyar_server_patch_installed=True
 log.info('NetYar server patch installed')
