"""Reliable Telegram request-code routing: always use the exact account that created the request."""
import asyncio,logging
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,MessageHandler,ApplicationHandlerStop,filters
log=logging.getLogger("netyar.telegram_partner_code_reliable")
MAX_CODE_REQUESTS=10

def install(app,B):
 if getattr(B,"_partner_code_reliable_installed",False):return
 def exact_chat(rid):
  try:
   import request_language_actions as L
   x=L.request_chat(B.db,rid)
   if x:return int(x)
  except Exception:pass
  try:
   x=B.db.setting(f"request_chat_{rid}","").strip();return int(x) if x else None
  except Exception:return None
 def partner_for(r):
  try:
   p=B.db.conn.execute("SELECT id,phone,name,active FROM partners WHERE id=? AND active=1",(r["user_id"],)).fetchone()
   if p:return p
  except Exception:pass
  return None
 def request_details(rid):
  rows=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
  labels={"phone":"📱 شماره موبایل مشترک","mobile":"📱 شماره موبایل مشترک","customer_phone":"📱 شماره موبایل مشترک","dob":"🎂 تاریخ تولد مشترک","birth_date":"🎂 تاریخ تولد مشترک","unique_id":"🆔 شناسه یکتا","unique_code":"🆔 شناسه یکتا","special_id":"🔖 شناسه اختصاصی","special_code":"🔖 شناسه اختصاصی","family_code":"👨‍👩‍👧‍👦 کد خانوار","household_code":"👨‍👩‍👧‍👦 کد خانوار","passport":"🛂 شماره پاسپورت","passport_number":"🛂 شماره پاسپورت","doc_type":"🪪 نوع مدرک","name":"👤 نام و نام خانوادگی","full_name":"👤 نام و نام خانوادگی"}
  lines=[]
  for a in rows:
   if a["answer"]:lines.append(f"{labels.get(a['field_key'], '📋 '+str(a['field_key']))}: {a['answer']}")
   elif a["file_id"]:lines.append(f"{labels.get(a['field_key'], '📋 '+str(a['field_key']))}: 📎 فایل پیوست")
  return "\n".join(lines) if lines else "• اطلاعات تکمیلی ثبت نشده است."
 async def ask(update,context):
  q=update.callback_query;data=str(q.data or "")
  if not data.startswith("panel:askcode:"):return
  if not B.admin(q.from_user.id):await q.answer("دسترسی ندارید",show_alert=True);raise ApplicationHandlerStop
  try:
   rid=int(data.rsplit(":",1)[1]);r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
   if not r:await q.answer("درخواست پیدا نشد",show_alert=True);raise ApplicationHandlerStop
   chat=exact_chat(rid)
   # Deliberately do NOT fall back to the first linked partner account.
   if not chat:
    await q.answer("❌ حساب تلگرام ثبت‌کننده این درخواست مشخص نیست.",show_alert=True);raise ApplicationHandlerStop
   n=int(B.db.setting(f"partner_code_attempts_{rid}","0") or 0)
   if n>=MAX_CODE_REQUESTS:await q.answer("سقف درخواست کد تکمیل شده است.",show_alert=True);raise ApplicationHandlerStop
   n+=1;B.db.set_setting(f"partner_code_attempts_{rid}",str(n));B.db.set_setting(f"partner_code_request_admin_{rid}",str(q.from_user.id));B.db.set_setting(f"request_code_chat_{rid}",str(chat))
   B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
   details=request_details(rid)
   msg=("👔 مدیریت\n\n📨 درخواست کد خدمت\n"f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n\n📋 اطلاعات درخواست:\n{details}\n\nلطفاً کد را همین‌جا ارسال کنید. فقط متن کد را بفرستید.")
   err=None
   for i in range(3):
    try:
     await context.bot.send_message(chat_id=chat,text=msg,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو",callback_data=f"pc:x:{rid}")]]));err=None;break
    except Exception as e:err=e;await asyncio.sleep(.7*(i+1))
   if err:raise err
   await q.answer("✅ درخواست کد دقیقاً برای همان حسابی که درخواست را ثبت کرده ارسال شد")
   await q.message.reply_text(f"✅ درخواست کد ارسال شد.\n🎫 {r['tracking_code']}")
  except ApplicationHandlerStop:raise
  except Exception:log.exception("ask partner code failed");await q.answer("❌ ارسال درخواست کد ناموفق بود.",show_alert=True)
  raise ApplicationHandlerStop
 async def reply(update,context):
  if not update.message or not update.message.text:return
  uid=update.effective_user.id;st=B.S.setdefault(uid,{})
  if st.get("mode")!="partner_send_code" or not st.get("code_request_rid"):return
  rid=int(st["code_request_rid"]);text=update.message.text.strip()
  if not text:await update.message.reply_text("❌ کد خالی است.");raise ApplicationHandlerStop
  r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
  if not r:st["mode"]=None;raise ApplicationHandlerStop
  exact=exact_chat(rid)
  if exact and int(exact)!=int(uid):return
  B.db.answer(rid,"partner_code",answer=text);B.db.conn.commit();B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
  aid=str(B.db.setting(f"partner_code_request_admin_{rid}","")).strip();recipients=[aid] if aid else [str(x) for x in B.ADM]
  details=request_details(rid)
  msg=("🔐 کد از همان حساب ثبت‌کننده دریافت شد\n\n"f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📱 حساب تلگرام ثبت‌کننده: {uid}\n\n📋 اطلاعات کامل درخواست:\n{details}\n\n🔑 کد: {text}")
  sent=False
  for x in recipients:
   if not x:continue
   for i in range(3):
    try:await context.bot.send_message(chat_id=int(x),text=msg);sent=True;break
    except Exception:
     if i<2:await asyncio.sleep(.7*(i+1))
  B.db.set_setting(f"partner_code_request_admin_{rid}","");B.db.set_setting(f"request_code_chat_{rid}","")
  st["mode"]=None;st.pop("code_request_rid",None);st.pop("code_request_admin",None)
  await update.message.reply_text("✅ کد دریافت شد و برای مدیریت ارسال شد." if sent else "⚠️ کد دریافت شد، اما اعلان مدیریت ارسال نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))
  raise ApplicationHandlerStop
 app.add_handler(CallbackQueryHandler(ask,pattern=r"^panel:askcode:\d+$"),group=-200)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,reply),group=-200)
 B._partner_code_reliable_installed=True
