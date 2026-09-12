import os,asyncio,logging,json,time,hashlib
from fastapi import FastAPI,Request
from app.config import PUBLIC_BASE_URL,RAILWAY_PUBLIC_DOMAIN
from app.db import init_db
logging.basicConfig(level=logging.INFO); log=logging.getLogger("netyar.server")
api=FastAPI(title="NetYar"); telegram_app=None; telegram_ready=False; rubika_ready=False
_telegram_queue=asyncio.Queue(maxsize=1000); _telegram_workers=[]
_RB_SEEN={}; _RB_SEEN_TTL=45

def public_url(path=""):
    base=(PUBLIC_BASE_URL or (f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else "")).rstrip("/")
    if not base: raise RuntimeError("Railway public domain is not set")
    return base+path

def _rb_inner(update):
    return update.get("update") if isinstance(update,dict) and isinstance(update.get("update"),dict) else update

def _rb_message(update):
    u=_rb_inner(update); m=(u.get("message") or u.get("new_message") or u) if isinstance(u,dict) else {}
    return m if isinstance(m,dict) else {}

def _rubika_text(update):
    m=_rb_message(update)
    for k in ("text","button_text"):
        if m.get(k): return str(m[k]).strip()
    a=m.get("aux_data")
    if isinstance(a,dict): return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip()
    return ""

def _rubika_chat(update):
    u=_rb_inner(update); m=_rb_message(u)
    return str((u.get("chat_id") if isinstance(u,dict) else "") or m.get("chat_id") or m.get("chat_key") or "")

def _rubika_user(update):
    u=_rb_inner(update); m=_rb_message(u); s=m.get("sender") or {}
    return str(s.get("user_id") or m.get("sender_id") or m.get("user_id") or _rubika_chat(u))

def _rb_event_key(update):
    """Stable dedupe key: ignore provider request/transport metadata."""
    u=_rb_inner(update); m=_rb_message(u)
    if not isinstance(u,dict): return repr(update)
    typ=str(u.get("type", "")); chat=_rubika_chat(u); user=_rubika_user(u)
    msg_id=str(m.get("message_id") or m.get("message_id") or u.get("message_id") or "")
    text=_rubika_text(u)
    if msg_id: raw=f"{typ}|{chat}|{user}|{msg_id}"
    else: raw=f"{typ}|{chat}|{user}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _rb_seen(key):
    now=time.time()
    for k,t in list(_RB_SEEN.items()):
        if now-t>_RB_SEEN_TTL: _RB_SEEN.pop(k,None)
    if key in _RB_SEEN: return True
    _RB_SEEN[key]=now; return False

@api.get("/health")
async def health(): return {"ok":True,"service":"NetYar","telegram":telegram_ready,"rubika":rubika_ready}

@api.post("/telegram/update")
async def telegram_update(request:Request):
    if telegram_app is None:return {"ok":False,"error":"telegram_not_ready"}
    try:
        from telegram import Update
        payload=await request.json(); update=Update.de_json(data=payload,bot=telegram_app.bot)
        if update is None:return {"ok":False,"error":"invalid_update"}
        try:_telegram_queue.put_nowait(update)
        except asyncio.QueueFull:return {"ok":False,"error":"telegram_queue_full"}
        return {"ok":True}
    except Exception:log.exception("Telegram webhook update failed");return {"ok":False,"error":"telegram_update_failed"}

async def _process_telegram_update(update):
    try:await telegram_app.process_update(update)
    except Exception:log.exception("Telegram background update processing failed")
async def _telegram_worker(n):
    while True:
        try:
            update=await _telegram_queue.get()
            try:await _process_telegram_update(update)
            finally:_telegram_queue.task_done()
        except asyncio.CancelledError:return
        except Exception:log.exception("Telegram worker %s failed",n)

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
    if l=="en": return [[("1","🪪 FIDA non-in-person"),("2","🖨 Printing")],[("3","🏛 Government access issue"),("4","🎫 Tracking")],[("5","📱 SIM services"),("6","📝 Screening test")],[("7","💰 My wallet"),("8","👥 Partner panel")],[("9","📞 Contact us"),("r","🔄 Restart")]]
    if l=="ar": return [[("1","🪪 خدمة فيدا"),("2","🖨 الطباعة")],[("3","🏛 مشكلة خدمات الحكومة"),("4","🎫 متابعة")],[("5","📱 خدمات الشريحة"),("6","📝 اختبار الفحص")],[("7","💰 محفظتي"),("8","👥 لوحة الشركاء")],[("9","📞 اتصل بنا"),("r","🔄 بدء من جديد")]]
    return [[("1","🪪 فیدای غیر حضوری"),("2","🖨 خدمات چاپ")],[("3","🏛 حل مشکل ورود اتباع دولت من"),("4","🎫 پیگیری")],[("5","📱 خدمات سیم کارت"),("6","📝 آزمون غربالگری")],[("7","💰 کیف پول من"),("8","👥 پنل همکاران")],[("9","📞 تماس با ما"),("r","🔄 شروع مجدد")]]

def _patch_rubika(rb):
    rb.rows=_safe_rubika_rows; rb.main_rows=lambda uid:_split_main_rows(rb,uid)
    if not getattr(rb,"_netyar_handle_fixed",False):
        original_handle=rb.handle
        def handle_fixed(uid,chat,x,u):
            x=str(x).strip()
            aliases={"📝 Screening test":"📝 آزمون غربالگری","📝 اختبار الفحص":"📝 آزمون غربالگری","🎫 Follow-up":"🎫 پیگیری","🎫 متابعة":"🎫 پیگیری","🔄 Restart":"🔄 شروع مجدد","🔄 بدء من جديد":"🔄 شروع مجدد"}
            x=aliases.get(x,x)
            if x in {"🔄 شروع مجدد","🔄 Restart"}:
                rb.STATE[str(uid)]={"lang":rb.STATE.get(str(uid),{}).get("lang","fa"),"step":"language"}
                return rb.send(chat,rb.TEXT["fa"]["lang"],[["1","🇮🇷 فارسی"],["2","🇬🇧 English"],["3","🇸🇦 العربية"]])
            if x=="📝 آزمون غربالگری" and rb.STATE.get(str(uid),{}).get("step")=="menu":return rb.send(chat,"⏳ آزمون غربالگری فعلاً غیرفعال است.",rb.main_rows(uid))
            if x in {"🎫 پیگیری","🎫 Tracking"} and rb.STATE.get(str(uid),{}).get("step")=="menu":rb.STATE[str(uid)]["step"]="track";return rb.send(chat,rb.T(uid,"track"),[[('0',rb.CANCEL)]])
            if x=="❌ انصراف":return rb.send(chat,"❌ عملیات لغو شد.",rb.main_rows(uid))
            return original_handle(uid,chat,x,u)
        rb.handle=handle_fixed;rb._netyar_handle_fixed=True

def _normalize_rubika_button(update,rb):
    raw=_rubika_text(update); uid=_rubika_user(update); st=rb.STATE.get(uid,{})
    if raw not in {str(i) for i in range(10)}: return update
    step=st.get("step") or st.get("mode") or ""
    maps={"language":{"1":"🇮🇷 فارسی","2":"🇬🇧 English","3":"🇸🇦 العربية"},"citizenship":{"1":"🪪 اتباع هستم","2":"🇮🇷 ایرانی هستم"},"iranian":{"1":"👥 پنل همکاران","2":"🎫 پیگیری"},"menu":{"1":"🪪 فیدای غیر حضوری","2":"🖨 خدمات چاپ","3":"🏛 حل مشکل ورود اتباع دولت من","4":"🎫 پیگیری","5":"📱 خدمات سیم کارت","6":"📝 آزمون غربالگری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","0":"❌ انصراف"},"partner":{"1":"➕ شارژ حساب","2":"🔎 پیگیری کد","3":"📋 سوابق","4":"💰 موجودی","5":"🏛 حل مشکل سامانه دولت من","0":rb.CANCEL}}
    label=maps.get(step,{}).get(raw)
    if label: _rb_message(update)["text"]=label
    return update

async def _run_rubika(update,rb):
    try:
        normalized=_normalize_rubika_button(update,rb); await asyncio.to_thread(rb.process,normalized); log.info("Rubika update processed: user=%s text=%s",_rubika_user(update),_rubika_text(normalized))
    except Exception:log.exception("Rubika background update processing failed")

@api.post("/rubika/update")
async def rubika_update(request:Request):
    raw=await request.body()
    if not raw:return {"ok":True}
    try:body=json.loads(raw.decode("utf-8"));update=_rb_inner(body)
    except Exception:return {"ok":True}
    if not isinstance(update,dict) or not update:return {"ok":True}
    try:
        import rubika_v2 as rb
        log.info("Rubika webhook received: type=%s user=%s",update.get("type","unknown"),_rubika_user(update))
        if _rb_seen(_rb_event_key(update)):return {"ok":True,"duplicate":True}
        _patch_rubika(rb)
        if update.get("type")=="StartedBot":
            msg=update.get("new_message") or update.get("message") or {};chat=str(update.get("chat_id") or msg.get("chat_id") or "");uid=str((msg or {}).get("sender_id") or (msg or {}).get("user_id") or chat)
            if chat:
                rb.STATE[uid]={"lang":"fa","step":"language"};asyncio.create_task(asyncio.to_thread(rb.send,chat,rb.TEXT["fa"]["lang"],[["1","🇮🇷 فارسی"],["2","🇬🇧 English"],["3","🇸🇦 العربية"]]));log.info("Rubika bot started: user=%s",uid)
        else:asyncio.create_task(_run_rubika(update,rb))
        return {"ok":True}
    except Exception:log.exception("Rubika webhook update failed");return {"ok":False,"error":"rubika_update_failed"}

@api.get("/rubika/update")
async def rubika_update_probe():return {"ok":True,"service":"NetYar","provider":"rubika"}
@api.head("/rubika/update")
async def rubika_update_head():return None
@api.post("/rubika/receiveUpdate")
async def rubika_receive_update(request:Request):return await rubika_update(request)
@api.get("/rubika/receiveUpdate")
async def rubika_receive_update_probe():return {"ok":True,"service":"NetYar","provider":"rubika"}
@api.head("/rubika/receiveUpdate")
async def rubika_receive_update_head():return None

async def _integration_watchdog():
    while True:
        try:
            await asyncio.sleep(90)
            if telegram_app is not None:
                try:
                    info=await telegram_app.bot.get_webhook_info()
                    if (info.url or "").strip():await telegram_app.bot.delete_webhook(drop_pending_updates=False)
                except Exception:log.exception("Telegram webhook watchdog failed")
        except asyncio.CancelledError:return
        except Exception:log.exception("integration watchdog failed")
