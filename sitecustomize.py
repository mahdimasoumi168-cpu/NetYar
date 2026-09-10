"""NetYar safe startup compatibility layer."""
import logging
log=logging.getLogger("netyar.sitecustomize")
try:
 import bot as B
 from telegram import ReplyKeyboardMarkup,InlineKeyboardMarkup,InlineKeyboardButton
 def safe_kb(rows): return ReplyKeyboardMarkup([[str(x) for x in (r or [])] for r in (rows or []) if r],resize_keyboard=True,one_time_keyboard=False)
 B.kb=safe_kb
 async def safe_notify(app,message,request_id=None,inline=None,files=None):
  if not B.ADM:return
  ids=list(files or [])
  if request_id:
   try: ids += [r["file_id"] for r in B.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",(request_id,)).fetchall() if r["file_id"]]
   except Exception: log.exception("request files")
  if request_id and inline is None: inline=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده درخواست",callback_data=f"req:v:{request_id}")],[InlineKeyboardButton("✅ تأیید خدمت",callback_data=f"req:a:{request_id}"),InlineKeyboardButton("❌ رد خدمت",callback_data=f"req:x:{request_id}")],[InlineKeyboardButton("🔐 درخواست کد از همکار",callback_data=f"req:p:{request_id}")],[InlineKeyboardButton("✉️ پاسخ",callback_data=f"req:r:{request_id}")]])
  for aid in B.ADM:
   try:
    await app.bot.send_message(chat_id=int(aid),text=message,reply_markup=inline)
    for fid in dict.fromkeys(ids):
     try: await app.bot.send_photo(chat_id=int(aid),photo=fid,caption=f"📎 فایل درخواست #{request_id}")
     except Exception:
      try: await app.bot.send_document(chat_id=int(aid),document=fid,caption=f"📎 فایل درخواست #{request_id}")
      except Exception: log.exception("admin file forwarding")
   except Exception: log.exception("admin notification")
 B.notify_admins=safe_notify
 _old_admin=B.admin_cb
 async def safe_admin(update,context):
  q=update.callback_query; d=(q.data or "").split(":")
  if not B.admin(q.from_user.id):return
  if len(d)>=3 and d[0]=="req":
   try: rid=int(d[2])
   except ValueError: await q.answer("درخواست نامعتبر");return
   r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
   if not r: await q.answer("درخواست پیدا نشد");return
   await q.answer()
   if d[1] in {"a","x"}:
    status="approved" if d[1]=="a" else "rejected";B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid));B.db.conn.commit()
    pr=B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(rid,)).fetchone();pid=str(pr["answer"]) if pr else ""
    if not pid:
     p=B.db.conn.execute("SELECT id FROM partners WHERE id=?",(r["user_id"],)).fetchone();pid=str(p["id"]) if p else ""
    chat=B.db.setting(f"partner_chat_{pid}","") if pid else "";msg="✅ خدمت شما توسط مدیریت تأیید شد." if status=="approved" else "❌ خدمت شما توسط مدیریت رد شد."
    if chat:
     try: await context.bot.send_message(chat_id=int(chat),text=msg,reply_markup=B.partner_kb())
     except Exception: log.exception("partner status")
    else:
     u=B.db.conn.execute("SELECT platform,external_id FROM users WHERE id=?",(r["user_id"],)).fetchone()
     if u and u["platform"]=="telegram":
      try: await context.bot.send_message(chat_id=int(u["external_id"]),text=msg)
      except Exception: log.exception("customer status")
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    return await q.message.reply_text("✅ خدمت تأیید شد و نتیجه ارسال شد." if status=="approved" else "❌ خدمت رد شد و نتیجه ارسال شد.",reply_markup=B.amenu())
   if d[1]=="p":
    pr=B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(rid,)).fetchone();pid=str(pr["answer"]) if pr else ""
    if not pid:
     p=B.db.conn.execute("SELECT id FROM partners WHERE id=?",(r["user_id"],)).fetchone();pid=str(p["id"]) if p else ""
    if not pid:return await q.message.reply_text("⚠️ این درخواست به همکار متصل نیست.",reply_markup=B.amenu())
    B.db.set_setting(f"partner_code_request_{pid}",f"{rid}|{B.now()}");chat=B.db.setting(f"partner_chat_{pid}","")
    if not chat:return await q.message.reply_text("⚠️ همکار هنوز یک‌بار وارد پنل نشده تا چت او ثبت شود.",reply_markup=B.amenu())
    try:
     await context.bot.send_message(chat_id=int(chat),text=f"🔐 مدیریت برای درخواست {r['tracking_code']} کد تأیید همان خدمت را می‌خواهد.\n\nفقط کد تأیید خدمت را بفرستید؛ رمز ورود پنل را ارسال نکنید.",reply_markup=B.partner_kb());return await q.message.reply_text("✅ درخواست کد برای همکار ارسال شد.",reply_markup=B.amenu())
    except Exception: log.exception("verification request");return await q.message.reply_text("❌ ارسال درخواست کد به همکار انجام نشد.",reply_markup=B.amenu())
  return await _old_admin(update,context)
 B.admin_cb=safe_admin
 _old_ptext=B.ptext
 async def safe_ptext(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{})
  if st.get("partner_id"):
   pid=st["partner_id"];B.db.set_setting(f"partner_chat_{pid}",str(update.effective_chat.id));pending=B.db.setting(f"partner_code_request_{pid}","")
   if pending:
    try:
     rid_s,ts=pending.split("|",1);from datetime import datetime,timezone,timedelta;created=datetime.strptime(ts,"%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
     if datetime.now(timezone.utc)-created>timedelta(minutes=5):B.db.set_setting(f"partner_code_request_{pid}","")
     else:
      text=(update.message.text or "").strip()
      if text and text not in {B.CANCEL,"لغو","❌ لغو"}:
       rid=int(rid_s);B.db.answer(rid,"verification_code",answer=text);B.db.set_setting(f"partner_code_request_{pid}","");B.db.conn.commit()
       for aid in B.ADM:
        try: await context.bot.send_message(chat_id=int(aid),text=f"🔐 کد تأیید همکار دریافت شد.\n🎫 درخواست: {rid}\n👥 همکار: {pid}\n🔑 کد: {text}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده",callback_data=f"req:v:{rid}"),InlineKeyboardButton("✅ تأیید",callback_data=f"req:a:{rid}"),InlineKeyboardButton("❌ رد",callback_data=f"req:x:{rid}")]]))
        except Exception: log.exception("verification notification")
       st["mode"]=None;return await update.message.reply_text("✅ کد دریافت شد و برای مدیریت ارسال شد.",reply_markup=B.partner_kb())
    except Exception:B.db.set_setting(f"partner_code_request_{pid}","");log.exception("verification state")
  return await _old_ptext(update,context)
 B.ptext=safe_ptext
 import telegram_runtime as TR
 _original_router=getattr(TR,"_original_router",B.router)
 async def safe_router(update,context):
  text=(update.message.text or "").strip();uid=update.effective_user.id;st=B.S.setdefault(uid,{});lang=st.get("lang","fa")
  screening={"fa":"📝 آزمون غربالگری","en":"📝 Screening test","ar":"📝 اختبار الفحص"}[lang];follow={"fa":"🎫 پیگیری","en":"🎫 Follow-up","ar":"🎫 متابعة"}[lang]
  if st.get("status")=="foreign" and st.get("mode") is None:
   if text==screening:return await update.message.reply_text(B.L(uid,"⏳ آزمون غربالگری فعلاً غیرفعال است.","⏳ Screening test is currently unavailable.","⏳ اختبار الفحص غير متاح حالياً."),reply_markup=B.main(uid))
   if text==follow:st["mode"]="ptrack";return await update.message.reply_text(B.L(uid,"🎫 کد پیگیری را وارد کنید.","🎫 Enter the tracking code.","🎫 أدخل رمز المتابعة."),reply_markup=B.cancel_kb())
  return await _original_router(update,context)
 B.router=safe_router
 log.info("NetYar safe Telegram runtime installed")
except Exception:log.exception("NetYar safe Telegram startup patch failed")
try:
 import json,rubika_v2 as RB
 def _message(u):
  if isinstance(u,dict) and isinstance(u.get("inline_message"),dict):return u["inline_message"]
  if isinstance(u,dict):
   m=u.get("message") or u.get("new_message") or u;return m if isinstance(m,dict) else {}
  return {}
 def _text(u):
  m=_message(u)
  for k in ("text","button_text"):
   if m.get(k):return str(m[k]).strip()
  a=m.get("aux_data")
  if isinstance(a,dict):return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip()
  if isinstance(a,str):
   try:
    a=json.loads(a)
    if isinstance(a,dict):return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip()
   except Exception:pass
  return ""
 RB.text_of=_text
 log.info("NetYar Rubika safe payload normalization installed")
except Exception:log.exception("NetYar Rubika startup patch failed")

# --- Partner chat binding fix ---
# A partner's chat id must be persisted immediately after successful login/menu access.
# Previously it was only written by the generic partner text handler, so the admin could
# know the partner id but still have no chat destination for a verification-code request.
try:
    _partner_original = B.partner
    async def _partner_with_chat(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        if pid:
            try:
                B.db.set_setting(f"partner_chat_{pid}", str(update.effective_chat.id))
                B.db.conn.commit()
                log.info("partner chat bound: partner_id=%s chat_id=%s", pid, update.effective_chat.id)
            except Exception:
                log.exception("partner chat binding failed")
        return await _partner_original(update, context)
    B.partner = _partner_with_chat
except Exception:
    log.exception("partner chat binding patch failed")
