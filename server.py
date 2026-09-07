import os,asyncio,logging,json
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
        payload=await request.json()
        update=Update.de_json(data=payload,bot=telegram_app.bot)
        await telegram_app.update_queue.put(update)
        log.info("Telegram update accepted: update_id=%s",payload.get("update_id"))
        return {"ok":True}
    except Exception:
        log.exception("Telegram webhook update failed")
        return {"ok":False}

def _rubika_text(update):
    m=update.get("message") or update.get("new_message") or update
    if not isinstance(m,dict): return ""
    for k in ("text","button_text"):
        if m.get(k): return str(m[k]).strip()
    a=m.get("aux_data")
    if isinstance(a,dict): return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip()
    if isinstance(a,str):
        try:
            a=json.loads(a)
            return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip() if isinstance(a,dict) else ""
        except Exception: return ""
    return ""

def _rubika_chat(update):
    m=update.get("message") or update.get("new_message") or update
    return str((m or {}).get("chat_id") or (m or {}).get("chat_key") or update.get("chat_id") or "")

def _rubika_user(update):
    m=update.get("message") or update.get("new_message") or update
    s=(m or {}).get("sender") or {}
    return str((s or {}).get("user_id") or (m or {}).get("sender_id") or (m or {}).get("user_id") or _rubika_chat(update))

def _safe_rubika_rows(rows):
    out=[]
    for row in rows or []:
        buttons=[]
        for i,item in enumerate(row or []):
            if isinstance(item,(tuple,list)) and len(item)>=2:
                bid,label=str(item[0]),str(item[1])
            else:
                bid,label=str(i),str(item)
            buttons.append({"id":bid,"type":"Simple","button_text":label})
        if buttons: out.append({"buttons":buttons})
    return out

def _patch_rubika(rb):
    rb.rows=_safe_rubika_rows

def _normalize_rubika_button(update,rb):
    raw=_rubika_text(update)
    if raw not in {str(i) for i in range(10)}: return update
    uid=_rubika_user(update)
    st=rb.STATE.get(uid,{})
    admin=uid in rb.ADMIN_IDS or st.get("admin") is True
    partner=bool(st.get("partner_id"))
    step=st.get("step") or st.get("mode") or ""
    maps={
      "main":{"1":"🪪 فیدای غیر حضوری","2":"🖨 خدمات چاپ","3":"🪪 حل مشکل ورود اتباع دولت من","4":"🎫 کد رهگیری تمدید کارت‌ها","5":"📱 خدمات سیم کارت","6":"📝 آزمون غربالگری و پیگیری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","0":rb.CANCEL},
      "partner":{"1":"➕ شارژ حساب","2":"🔎 پیگیری کد","3":"📋 سوابق","4":"💰 موجودی","5":"🏛 حل مشکل سامانه دولت من","0":rb.CANCEL},
      "admin":{"1":"👥 همکاران","2":"💰 شارژها","3":"📋 درخواست‌ها","4":"💳 پرداخت‌های مشتری","5":"⚙️ قیمت‌ها","6":"🤖 افزودن بات","7":"🤖 بات‌های متصل","8":"📊 گزارش","0":"⬅️ منوی اصلی"}}
    if admin and not partner and step in {"admin","admin_price","bot_platform","bot_name","bot_api"}:
        key="admin"
    elif partner and step=="partner":
        key="partner"
    else:
        key="main"
    label=maps[key].get(raw)
    if not label:return update
    m=update.get("message") or update.get("new_message")
    if isinstance(m,dict): m["text"]=label
    return update

async def _run_rubika(update,rb):
    try:
        normalized=_normalize_rubika_button(update,rb)
        await asyncio.to_thread(rb.process,normalized)
        log.info("Rubika update processed: type=%s text=%s",update.get("type"),_rubika_text(update))
    except Exception:
        log.exception("Rubika background update processing failed")

@api.post("/rubika/update")
async def rubika_update(request:Request):
    try:
        update=await request.json()
        import rubika_v2 as rb
        _patch_rubika(rb)
        if isinstance(update,dict) and update.get("type")=="StartedBot":
            msg=update.get("new_message") or update.get("message") or {}
            chat=str(update.get("chat_id") or msg.get("chat_id") or "")
            uid=str((msg or {}).get("sender_id") or (msg or {}).get("user_id") or chat)
            if chat:
                st=rb.STATE.setdefault(uid,{})
                if not st.get("lang") or st.get("step") in {None,""}:
                    st.clear(); st.update({"lang":"fa","step":"language"})
                    asyncio.create_task(asyncio.to_thread(rb.send,chat,rb.T(uid,"lang"),[["1","🇮🇷 فارسی"],["2","🇬🇧 English"],["3","🇸🇦 العربية"]]))
                elif st.get("step")=="language":
                    asyncio.create_task(asyncio.to_thread(rb.send,chat,rb.T(uid,"lang"),[["1","🇮🇷 فارسی"],["2","🇬🇧 English"],["3","🇸🇦 العربية"]]))
        else:
            asyncio.create_task(_run_rubika(update,rb))
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
        _patch_rubika(rb)
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
        try: await telegram_app.bot.delete_webhook(drop_pending_updates=False)
        except Exception: pass
        try: await telegram_app.stop()
        except Exception: pass
        try: await telegram_app.shutdown()
        except Exception: pass
    telegram_app=None

def main():
    import uvicorn
    uvicorn.run(api,host="0.0.0.0",port=int(os.getenv("PORT","8080")),log_level="info")

if __name__=="__main__": main()
