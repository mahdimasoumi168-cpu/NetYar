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
    if telegram_app is None:
        log.error("Telegram webhook called before Telegram application was ready")
        return {"ok":False,"error":"telegram_not_ready"}
    try:
        from telegram import Update
        payload=await request.json()
        update=Update.de_json(data=payload,bot=telegram_app.bot)
        if update is None:
            log.error("Telegram webhook received an empty/invalid update")
            return {"ok":False,"error":"invalid_update"}
        await telegram_app.update_queue.put(update)
        log.info("Telegram update accepted: update_id=%s kind=%s",payload.get("update_id"),"callback_query" if payload.get("callback_query") else "message" if payload.get("message") else "other")
        return {"ok":True}
    except Exception:
        log.exception("Telegram webhook update failed")
        return {"ok":False,"error":"telegram_update_failed"}

def _rubika_inner(update):
    if isinstance(update,dict) and isinstance(update.get("update"),dict):return update["update"]
    return update

def _rubika_message(update):
    u=_rubika_inner(update)
    if not isinstance(u,dict):return {}
    m=u.get("message") or u.get("new_message") or u
    return m if isinstance(m,dict) else {}

def _rubika_text(update):
    m=_rubika_message(update)
    for k in ("text","button_text"):
        if m.get(k):return str(m[k]).strip()
    a=m.get("aux_data")
    if isinstance(a,dict):return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip()
    if isinstance(a,str):
        try:
            a=json.loads(a); return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip() if isinstance(a,dict) else ""
        except Exception:return ""
    return ""

def _rubika_chat(update):
    u=_rubika_inner(update);m=_rubika_message(u)
    return str(m.get("chat_id") or m.get("chat_key") or (u.get("chat_id") if isinstance(u,dict) else "") or "")

def _rubika_user(update):
    u=_rubika_inner(update);m=_rubika_message(u);s=m.get("sender") or {}
    return str(s.get("user_id") or m.get("sender_id") or m.get("user_id") or _rubika_chat(u))

def _safe_rubika_rows(rows):
    out=[]
    for row in rows or []:
        buttons=[]
        for i,item in enumerate(row or []):
            if isinstance(item,(tuple,list)) and len(item)>=2:bid,label=str(item[0]),str(item[1])
            else:bid,label=str(i),str(item)
            buttons.append({"id":bid,"type":"Simple","button_text":label})
        if buttons:out.append({"buttons":buttons})
    return out

def _split_main_rows(rb,uid):
    l=rb.STATE.get(str(uid),{}).get("lang","fa")
    if l=="en":return [[("1","🪪 FIDA non-in-person"),("2","🖨 Printing")],[("3","🏛 Government access issue"),("4","🎫 Tracking")],[("5","📱 SIM services"),("6","📝 Screening test")],[("7","💰 My wallet"),("8","👥 Partner panel")],[("9","📞 Contact us"),("0","❌ Cancel")]]
    if l=="ar":return [[("1","🪪 خدمة فيدا"),("2","🖨 الطباعة")],[("3","🏛 مشكلة خدمات الحكومة"),("4","🎫 متابعة")],[("5","📱 خدمات الشريحة"),("6","📝 اختبار الفحص")],[("7","💰 محفظتي"),("8","👥 لوحة الشركاء")],[("9","📞 اتصل بنا"),("0","❌ إلغاء")]]
    return [[("1","🪪 فیدای غیر حضوری"),("2","🖨 خدمات چاپ")],[("3","🏛 حل مشکل ورود اتباع دولت من"),("4","🎫 پیگیری")],[("5","📱 خدمات سیم کارت"),("6","📝 آزمون غربالگری")],[("7","💰 کیف پول من"),("8","👥 پنل همکاران")],[("9","📞 تماس با ما"),("0",rb.CANCEL)]]

def _patch_rubika(rb):
    rb.rows=_safe_rubika_rows
    rb.main_rows=lambda uid:_split_main_rows(rb,uid)
    if not getattr(rb,"_netyar_admin_fixed",False):
        original_admin=rb.admin
        def admin_fixed(uid,chat,x):
            st=rb.STATE.get(str(uid),{})
            if st.get("step")=="bot_api":
                token=str(x).strip()
                if not token:return rb.send(chat,rb.T(uid,"bot_api"),[[('0',rb.CANCEL)]])
                rb.db.add_bot(st.get("bot_platform","unknown"),st.get("bot_name","Bot"),token)
                st["step"]="admin"
                return rb.send(chat,rb.T(uid,"bot_saved",name=st.get("bot_name","Bot"),platform=st.get("bot_platform","unknown")),rb.admin_rows())
            return original_admin(uid,chat,x)
        rb.admin=admin_fixed
        rb._netyar_admin_fixed=True
    if not getattr(rb,"_netyar_handle_fixed",False):
        original_handle=rb.handle
        def handle_fixed(uid,chat,x,u):
            if x in {"📝 آزمون غربالگری","📝 Screening test","📝 اختبار الفحص"} and rb.STATE.get(str(uid),{}).get("step")=="menu":
                return rb.send(chat,"⏳ آزمون غربالگری فعلاً غیرفعال است.",rb.main_rows(uid))
            return original_handle(uid,chat,x,u)
        rb.handle=handle_fixed
        rb._netyar_handle_fixed=True

def _normalize_rubika_button(update,rb):
    raw=_rubika_text(update)
    if raw not in {str(i) for i in range(10)}:return update
    uid=_rubika_user(update);st=rb.STATE.get(uid,{})
    step=st.get("step") or st.get("mode") or ""
    maps={
      "language":{"1":"🇮🇷 فارسی","2":"🇬🇧 English","3":"🇸🇦 العربية"},
      "citizenship":{"1":"🪪 اتباع هستم","2":"🇮🇷 ایرانی هستم"},
      "iranian":{"1":"👥 پنل همکاران","2":"🎫 پیگیری"},
      "menu":{"1":"🪪 فیدای غیر حضوری","2":"🖨 خدمات چاپ","3":"🏛 حل مشکل ورود اتباع دولت من","4":"🎫 پیگیری","5":"📱 خدمات سیم کارت","6":"📝 آزمون غربالگری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","0":rb.CANCEL},
      "partner":{"1":"➕ شارژ حساب","2":"🔎 پیگیری کد","3":"📋 سوابق","4":"💰 موجودی","5":"🏛 حل مشکل سامانه دولت من","0":rb.CANCEL},
      "admin":{"1":"👥 همکاران","2":"💰 شارژها","3":"📋 درخواست‌ها","4":"💳 پرداخت‌های مشتری","5":"⚙️ قیمت‌ها","6":"🤖 افزودن بات","7":"🤖 بات‌های متصل","8":"📊 گزارش","0":"⬅️ منوی اصلی"},
      "print_color":{"1":"⚫ سیاه و سفید","2":"🌈 رنگی","0":rb.CANCEL},
      "print_side":{"1":"📄 یک‌رو","2":"🔄 پشت‌ورو","0":rb.CANCEL},
      "print_files":{"1":"✅ تأیید","0":rb.CANCEL},
      "print":{"1":"✅ تأیید","0":rb.CANCEL},
      "topup_amount":{"0":rb.CANCEL},"topup_receipt":{"0":rb.CANCEL},"track":{"0":rb.CANCEL},"track_partner":{"0":rb.CANCEL},"partner_phone":{"0":rb.CANCEL},"partner_pass":{"0":rb.CANCEL},"gov_fida":{"0":rb.CANCEL},"partner_gov_fida":{"0":rb.CANCEL},"gov_yekta":{"0":rb.CANCEL},"gov_dob":{"0":rb.CANCEL},"fida_doc":{"0":rb.CANCEL}}
    table=maps.get(step)
    if not table:return update
    label=table.get(raw)
    if not label:return update
    target=_rubika_inner(update);m=_rubika_message(target)
    if isinstance(m,dict):m["text"]=label
    return update

async def _run_rubika(update,rb):
    try:
        normalized=_normalize_rubika_button(update,rb)
        log.info("Rubika update accepted: type=%s chat=%s text=%s",_rubika_inner(update).get("type") if isinstance(_rubika_inner(update),dict) else None,_rubika_chat(update),_rubika_text(normalized))
        await asyncio.to_thread(rb.process,normalized)
        log.info("Rubika update processed: chat=%s text=%s",_rubika_chat(update),_rubika_text(normalized))
    except Exception:
        log.exception("Rubika background update processing failed")

@api.post("/rubika/update")
async def rubika_update(request:Request):
    try:
        body=await request.json();update=_rubika_inner(body)
        import rubika_v2 as rb
        _patch_rubika(rb)
        if isinstance(update,dict) and update.get("type")=="StartedBot":
            msg=update.get("new_message") or update.get("message") or {};chat=str(update.get("chat_id") or msg.get("chat_id") or "");uid=str((msg or {}).get("sender_id") or (msg or {}).get("user_id") or chat)
            if chat:
                st=rb.STATE.setdefault(uid,{});st.clear();st.update({"lang":"fa","step":"language"})
                log.info("Rubika StartedBot: chat=%s user=%s",chat,uid)
                asyncio.create_task(asyncio.to_thread(rb.send,chat,rb.TEXT["fa"]["lang"],[["1","🇮🇷 فارسی"],["2","🇬🇧 English"],["3","🇸🇦 العربية"]]))
        else:
            asyncio.create_task(_run_rubika(update,rb))
        return {"ok":True}
    except Exception:
        log.exception("Rubika webhook update failed")
        return {"ok":False,"error":"rubika_update_failed"}

@api.on_event("startup")
async def startup():
    global telegram_app,telegram_ready,rubika_ready
    init_db()
    try:
        import telegram_runtime as tg
        telegram_app=tg.build();await telegram_app.initialize();await telegram_app.start();tg_url=public_url("/telegram/update");secret=os.getenv("TELEGRAM_WEBHOOK_SECRET","").strip() or None
        await telegram_app.bot.set_webhook(url=tg_url,allowed_updates=None,secret_token=secret)
        info=await telegram_app.bot.get_webhook_info()
        telegram_ready=True
        log.info("Telegram webhook registered: url_set=%s pending=%s last_error=%s",bool(info.url),info.pending_update_count,info.last_error_message or "none")
    except Exception:
        log.exception("Telegram webhook startup failed")
        telegram_ready=False
    try:
        import rubika_v2 as rb
        _patch_rubika(rb);endpoint=public_url("/rubika/update");result=rb.call("updateBotEndpoints",{"url":endpoint,"type":"ReceiveUpdate"});log.info("Rubika ReceiveUpdate endpoint registered: %s | %s",endpoint,result);log.info("Rubika getMe: %s",rb.call("getMe"));rubika_ready=True
    except Exception:
        log.exception("Rubika webhook registration failed")
        rubika_ready=False

@api.on_event("shutdown")
async def shutdown():
    global telegram_app
    if telegram_app is not None:
        try:await telegram_app.bot.delete_webhook(drop_pending_updates=False)
        except Exception:pass
        try:await telegram_app.stop()
        except Exception:pass
        try:await telegram_app.shutdown()
        except Exception:pass
    telegram_app=None

def main():
    import uvicorn
    uvicorn.run(api,host="0.0.0.0",port=int(os.getenv("PORT","8080")),log_level="info")
if __name__=="__main__":main()
