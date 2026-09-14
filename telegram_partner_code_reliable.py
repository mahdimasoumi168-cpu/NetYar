"""Reliable Telegram partner-code request/return flow."""
import asyncio, logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters
log=logging.getLogger("netyar.telegram_partner_code_reliable")
MAX_CODE_REQUESTS=10

def install(app,B):
 if getattr(B,"_partner_code_reliable_installed",False): return
 def state(uid): return B.S.setdefault(uid,{}) if uid in B.S else B.S.setdefault(str(uid),{})
 async def partner_for(r):
  try:
   p=B.db.conn.execute("SELECT id,phone,name,active FROM partners WHERE id=? AND active=1",(r["user_id"],)).fetchone()
   if p:return p
  except Exception:pass
  try:
   u=B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram'",(r["user_id"],)).fetchone(); ext=str(u["external_id"] or "").strip() if u else ""
   if ext:
    for p in B.db.conn.execute("SELECT id,phone,name,active FROM partners WHERE active=1").fetchall():
     if ext in {str(B.db.setting(f"partner_chat_{p['id']}","")).strip(),str(B.db.setting(f"partner_chat_{p['phone']}","")).strip()}:return p
  except Exception:log.exception("partner resolution failed")
  try:
   x=B.db.setting(f"request_partner_{r['id']}","").strip()
   if x.isdigit():return B.db.conn.execute("SELECT id,phone,name,active FROM partners WHERE id=? AND active=1",(int(x),)).fetchone()
  except Exception:pass
  return None
 async def partner_chat(p):
  for key in (f"partner_chat_{p['id']}",f"partner_chat_{p['phone']}"):
   x=B.db.setting(key,"").strip()
   if x:
    try:return int(x)
    except Exception:pass
  return None
 async def ask(update,context):
  q=update.callback_query; data=str(q.data or "")
  if not data.startswith("panel:askcode:"):return
  if not B.admin(q.from_user.id):await q.answer("دسترسی ندارید",show_alert=True);raise ApplicationHandlerStop
  try:
   rid=int(data.rsplit(":",1)[1]);r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
   if not r:await q.answer("درخواست پیدا نشد",show_alert=True);raise ApplicationHandlerStop
   p=await partner_for(r)
   if not p:await q.answer("همکار فعال برای این درخواست پیدا نشد",show_alert=True);raise ApplicationHandlerStop
   chat=await partner_chat(p)
   if not chat:await q.answer("چت تلگرام همکار ثبت نشده؛ همکار یک‌بار وارد پنل شود.",show_alert=True);raise ApplicationHandlerStop
   n=int(B.db.setting(f"partner_code_attempts_{rid}","0") or 0)
   if n>=MAX_CODE_REQUESTS:await q.answer("سقف درخواست کد تکمیل شده است.",show_alert=True);raise ApplicationHandlerStop
   n+=1
   B.db.set_setting(f"partner_code_attempts_{rid}",str(n));B.db.set_setting(f"partner_code_request_admin_{rid}",str(q.from_user.id));B.db.set_setting(f"request_partner_{rid}",str(p["id"]));B.db.set_setting(f"partner_code_request_{p['id']",f"{rid}|{r['tracking_code']}")
   B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
   st=state(chat);st.update(partner_id=int(p["id"]),partner_active=True,mode="partner_send_code",code_request_rid=rid,code_request_admin=int(q.from_user.id),lang=st.get("lang","fa"))
   msg=("👔 مدیریت\n\n📨 درخواست کد خدمت\n"f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n\nلطفاً کد خدمت/کد انجام کار را همین‌جا ارسال کنید. فقط متن کد را بفرستید.")
   err=None
   for i in range(3):
    try:await context.bot.send_message(chat_id=chat,text=msg,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو",callback_data=f"pc:x:{rid}:{p['id']}")]]));err=None;break
    except Exception as e:err=e;await asyncio.sleep(.7*(i+1))
   if err:raise err
   await q.answer("✅ درخواست کد برای همکار ارسال شد");await q.message.reply_text(f"✅ درخواست کد برای «{p['name'] or p['phone']}» ارسال شد.\n🎫 {r['tracking_code']}")
  except ApplicationHandlerStop:raise
  except Exception:log.exception("ask partner code failed");await q.answer("❌ ارسال درخواست کد ناموفق بود.",show_alert=True)
  raise ApplicationHandlerStop
 async def reply(update,context):
  if not update.message or not update.message.text:return
  uid=update.effective_user.id;st=state(uid)
  if st.get("mode")!="partner_send_code" or not st.get("partner_id") or not st.get("code_request_rid"):return
  rid=int(st["code_request_rid"]);text=update.message.text.strip()
  if not text:await update.message.reply_text("❌ کد خالی است.");raise ApplicationHandlerStop
  r=B.db.conn.execute("SELECT tracking_code,service_key FROM requests WHERE id=?",(rid,)).fetchone();p=B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?",(int(st["partner_id"]),)).fetchone()
  if not r:st["mode"]=None;raise ApplicationHandlerStop
  B.db.answer(rid,"partner_code",answer=text);B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
  aid=str(B.db.setting(f"partner_code_request_admin_{rid}","")).strip();recipients=[aid] if aid else [str(x) for x in B.ADM]
  msg=("🔐 کد از همکار دریافت شد\n\n"f"👤 همکار: {p['name'] if p else '-'}\n📱 شماره: {p['phone'] if p else '-'}\n🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n🔑 کد: {text}")
  sent=False
  for x in recipients:
   if not x:continue
   for i in range(3):
    try:await context.bot.send_message(chat_id=int(x),text=msg);sent=True;break
    except Exception:
     if i<2:await asyncio.sleep(.7*(i+1))
  B.db.set_setting(f"partner_code_request_admin_{rid}","");B.db.set_setting(f"partner_code_request_{st['partner_id']}","")
  st["mode"]=None;st.pop("code_request_rid",None);st.pop("code_request_admin",None)
  await update.message.reply_text("✅ کد دریافت شد و برای مدیریت ارسال شد." if sent else "⚠️ کد دریافت شد، اما اعلان مدیریت ارسال نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))
  raise ApplicationHandlerStop
 app.add_handler(CallbackQueryHandler(ask,pattern=r"^panel:askcode:\d+$"),group=-200)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,reply),group=-200)
 B._partner_code_reliable_installed=True
