import os,asyncio,logging
from fastapi import FastAPI,Request
from app.config import PUBLIC_BASE_URL,RAILWAY_PUBLIC_DOMAIN
from app.db import init_db

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("netyar.server")
api=FastAPI(title="NetYar")
telegram_app=None
telegram_ready=False
rubika_ready=False

def public_url(path=""):
    base=(PUBLIC_BASE_URL or (f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else "")).rstrip("/")
    if not base: raise RuntimeError("Railway public domain is not set")
    return base+path

@api.get("/health")
async def health():
    return {"ok":True,"service":"NetYar","telegram":telegram_ready,"rubika":rubika_ready}

@api.post("/telegram/update")
async def telegram_update(request:Request):
    if telegram_app is None: return {"ok":False,"error":"telegram_not_ready"}
    try:
        from telegram import Update
        data=await request.json()
        await telegram_app.update_queue.put(Update.de_json(data=data,bot=telegram_app.bot))
        return {"ok":True}
    except Exception:
        log.exception("Telegram webhook update failed")
        return {"ok":False}

@api.post("/rubika/update")
async def rubika_update(request:Request):
    try:
        update=await request.json()
        from rubika_v2 import process,STATE,T,send
        # Rubika StartedBot can arrive without message.text; initialize language explicitly.
        if isinstance(update,dict) and update.get("type")=="StartedBot":
            msg=update.get("new_message") or update.get("message") or {}
            chat=str(update.get("chat_id") or msg.get("chat_id") or "")
            uid=str(msg.get("sender_id") or msg.get("user_id") or chat)
            if chat:
                STATE[uid]={"lang":"fa","step":"language"}
                send(chat,T["fa"]["lang"],[[("1","🇮🇷 فارسی"),("2","🇬🇧 English"),("3","🇸🇦 العربية")]])
        else:
            await asyncio.to_thread(process,update)
        return {"ok":True}
    except Exception:
        log.exception("Rubika webhook update failed")
        return {"ok":False}

@api.on_event("startup")
async def startup():
    global telegram_app,telegram_ready,rubika_ready
    init_db()
    try:
        import telegram_runtime as tg
        telegram_app=tg.build()
        await telegram_app.initialize()
        await telegram_app.start()
        tg_url=public_url("/telegram/update")
        secret=os.getenv("TELEGRAM_WEBHOOK_SECRET","").strip() or None
        await telegram_app.bot.set_webhook(url=tg_url,allowed_updates=None,secret_token=secret)
        telegram_ready=True
        log.info("Telegram webhook registered: %s",tg_url)
    except Exception:
        log.exception("Telegram webhook startup failed")
        telegram_ready=False
    try:
        import rubika_v2 as rb
        endpoint=public_url("/rubika/update")
        result=rb.call("updateBotEndpoints",{"url":endpoint,"type":"ReceiveUpdate"})
        log.info("Rubika ReceiveUpdate endpoint registered: %s | %s",endpoint,result)
        log.info("Rubika getMe: %s",rb.call("getMe"))
        rubika_ready=True
    except Exception:
        log.exception("Rubika webhook registration failed")
        rubika_ready=False

@api.on_event("shutdown")
async def shutdown():
    global telegram_app
    if telegram_app is not None:
        try:
            await telegram_app.bot.delete_webhook(drop_pending_updates=False)
        except Exception: pass
        try:
            await telegram_app.stop()
        except Exception: pass
        try:
            await telegram_app.shutdown()
        except Exception: pass
    telegram_app=None

def main():
    import uvicorn
    uvicorn.run(api,host="0.0.0.0",port=int(os.getenv("PORT","8080")),log_level="info")

if __name__=="__main__":
    main()
