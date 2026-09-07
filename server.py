import os,sys,subprocess,threading,asyncio,json,logging,time
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from app.config import PUBLIC_BASE_URL,RAILWAY_PUBLIC_DOMAIN,SIZPAY_MERCHANT_ID,SIZPAY_TERMINAL_ID
from app.db import init_db,get_payment,set_result
from app.sizpay import confirm,payment_post_html

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("netyar.server")
api=FastAPI(title="NetYar")
children=[]
rubika_ready=False

def public_url(path=""):
    base=(PUBLIC_BASE_URL or (f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else "")).rstrip("/")
    if not base: raise RuntimeError("Railway public domain is not set")
    return base+path

def children_alive(name):
    for p,n in children:
        if n==name:return p.poll() is None
    return False

@api.get("/health")
async def health():
    return {"ok":True,"service":"NetYar","telegram":children_alive("telegram"),"rubika":rubika_ready}

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

@api.post("/rubika/update")
async def rubika_update(request:Request):
    try:
        update=await request.json()
        from rubika_v2 import process,STATE,T,send,lang,main_rows
        # StartedBot may have no message.text; initialize the conversation explicitly.
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

def start_child(cmd,name):
    env=os.environ.copy()
    env.pop("TELEGRAM_WEBHOOK_URL",None)
    p=subprocess.Popen([sys.executable,cmd],env=env)
    children.append((p,name))
    log.info("started %s pid=%s",name,p.pid)
    return p

def monitor():
    while True:
        time.sleep(5)
        for p,name in list(children):
            if p.poll() is not None:
                try: children.remove((p,name))
                except ValueError: pass
                if name=="telegram":
                    try:
                        children.append((subprocess.Popen([sys.executable,"telegram_runtime.py"],env={**os.environ,"TELEGRAM_WEBHOOK_URL":""}),name))
                    except Exception: log.exception("telegram restart failed")

def register_rubika_webhook():
    global rubika_ready
    try:
        import rubika_v2 as bot
        endpoint=public_url("/rubika/update")
        result=bot.call("updateBotEndpoints",{"url":endpoint,"type":"ReceiveUpdate"})
        log.info("Rubika ReceiveUpdate endpoint registered: %s",endpoint)
        log.info("Rubika getMe: %s",bot.call("getMe"))
        rubika_ready=True
        return result
    except Exception:
        log.exception("Rubika webhook registration failed")
        rubika_ready=False
        return None

def main():
    init_db()
    start_child("telegram_runtime.py","telegram")
    register_rubika_webhook()
    threading.Thread(target=monitor,daemon=True).start()
    import uvicorn
    uvicorn.run(api,host="0.0.0.0",port=int(os.getenv("PORT","8080")),log_level="info")

if __name__=="__main__":
    main()
