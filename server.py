import os,asyncio,logging
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from app.config import PUBLIC_BASE_URL,RAILWAY_PUBLIC_DOMAIN,SIZPAY_MERCHANT_ID,SIZPAY_TERMINAL_ID
from app.db import init_db,get_payment,set_result
from app.sizpay import confirm,payment_post_html

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

@api.get("/pay/{order_id}",response_class=HTMLResponse)
async def pay(order_id:str):
    row=get_payment(order_id)
    if not row or not row["token"]: return HTMLResponse("<h3>سفارش پیدا نشد یا توکن منقضی شده است.</h3>",status_code=404)
    if row["status"]!="pending": return HTMLResponse("<h3>این سفارش قبلاً پردازش شده است.</h3>",status_code=409)
    return HTMLResponse(payment_post_html(SIZPAY_MERCHANT_ID,SIZPAY_TERMINAL_ID,row["token"]))

async def callback_data(data):
    order_id=data.get("InvoiceNo",""); token=data.get("Token",""); row=get_payment(order_id)
    if not row:return HTMLResponse("<h3>سفارش معتبر نیست.</h3>",status_code=400)
    if row["status"]=="paid":return HTMLResponse("<h3>پرداخت قبلاً تأیید شده است.</h3>")
    if data.get("ResCod") not in {"0","00"}:
        set_result(order_id,"failed",data.get("Message","پرداخت ناموفق")); return HTMLResponse("<h3>❌ پرداخت ناموفق یا لغو شد.</h3>")
    if not token:return HTMLResponse("<h3>❌ توکن تراکنش دریافت نشد.</h3>",status_code=400)
    try:
        result=await asyncio.to_thread(confirm,token); code=str(result.get("ResCod","")).strip(); amount=int(result.get("Amount") or 0)
        if code not in {"0","00"}: set_result(order_id,"failed",result.get("Message","Confirm failed")); return HTMLResponse("<h3>❌ تأیید پرداخت ناموفق بود.</h3>")
        if amount and amount!=int(row["amount_rial"]): set_result(order_id,"failed","Amount mismatch"); return HTMLResponse("<h3>❌ مبلغ تراکنش با سفارش مطابقت ندارد.</h3>",status_code=400)
        set_result(order_id,"paid",result.get("Message","پرداخت تأیید شد"),trans_no=result.get("TransNo"),ref_no=result.get("RefNo"),trace_no=result.get("TraceNo"))
        return HTMLResponse("<h2>✅ پرداخت با موفقیت تأیید شد.</h2><p>اکنون به ربات برگردید.</p>")
    except Exception as e:
        set_result(order_id,"error",str(e)[:500]); return HTMLResponse("<h3>❌ خطا در تأیید تراکنش.</h3>",status_code=502)

@api.post("/sizpay/callback")
async def sizpay_callback_post(request:Request): return await callback_data({k:str(v) for k,v in (await request.form()).items()})

@api.get("/sizpay/callback")
async def sizpay_callback_get(request:Request): return await callback_data({k:str(v) for k,v in request.query_params.items()})

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
