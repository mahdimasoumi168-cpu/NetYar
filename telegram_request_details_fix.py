"""Complete Telegram request-details renderer with per-request language."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop
log=logging.getLogger("netyar.telegram.request_details")
FIELD_NAMES={
 "fa":{"doc_type":"🪪 نوع مدرک","phone":"📱 موبایل مشترک","dob":"🎂 تاریخ تولد","unique_id":"🆔 شناسه یکتا","special_id":"🔖 شناسه اختصاصی","family_code":"👨‍👩‍👧‍👦 کد خانوار","postal_code":"📮 کد پستی منزل","passport":"🛂 شماره/اطلاعات پاسپورت","gov_passport":"🛂 اطلاعات پاسپورت","partner_code":"🔐 کد خدمت","service_code":"🔐 کد خدمت","address":"🏠 نشانی","name":"👤 نام و نام خانوادگی","first_name":"👤 نام","last_name":"👤 نام خانوادگی","national_code":"🆔 کد ملی","document":"📎 مدرک"},
 "en":{"doc_type":"🪪 Document Type","phone":"📱 Customer Mobile","dob":"🎂 Date of Birth","unique_id":"🆔 Unique ID","special_id":"🔖 Special ID","family_code":"👨‍👩‍👧‍👦 Family Code","postal_code":"📮 Home Postal Code","passport":"🛂 Passport Number/Information","gov_passport":"🛂 Passport Information","partner_code":"🔐 Service Code","service_code":"🔐 Service Code","address":"🏠 Address","name":"👤 Full Name","first_name":"👤 First Name","last_name":"👤 Last Name","national_code":"🆔 National ID","document":"📎 Document"},
 "ar":{"doc_type":"🪪 نوع الوثيقة","phone":"📱 هاتف المشترك","dob":"🎂 تاريخ الميلاد","unique_id":"🆔 المعرّف الفريد","special_id":"🔖 المعرّف الخاص","family_code":"👨‍👩‍👧‍👦 رمز الأسرة","postal_code":"📮 الرمز البريدي للمنزل","passport":"🛂 رقم/معلومات جواز السفر","gov_passport":"🛂 معلومات جواز السفر","partner_code":"🔐 رمز الخدمة","service_code":"🔐 رمز الخدمة","address":"🏠 العنوان","name":"👤 الاسم الكامل","first_name":"👤 الاسم","last_name":"👤 اسم العائلة","national_code":"🆔 الرقم الوطني","document":"📎 الوثيقة"},
}
STATUS={"fa":{"awaiting_payment":"در انتظار پرداخت","submitted":"ثبت شده","new":"جدید","processing":"در حال بررسی","completed":"انجام شد","rejected":"رد شده"},"en":{"awaiting_payment":"Awaiting Payment","submitted":"Submitted","new":"New","processing":"Under Review","completed":"Completed","rejected":"Rejected"},"ar":{"awaiting_payment":"بانتظار الدفع","submitted":"تم التسجيل","new":"جديد","processing":"قيد المراجعة","completed":"تم الإنجاز","rejected":"مرفوض"}}

def _lang(B,rid):
 try:
  import request_language_actions as L
  return L.request_language(B.db,rid)
 except Exception:return "fa"
def _label(key,lang):
 key=str(key or "").strip(); return FIELD_NAMES.get(lang,FIELD_NAMES["fa"]).get(key, f"📋 {key.replace('_',' ')}")
def _buttons(rid,lang):
 try:
  import request_language_actions as L
  return L.admin_markup(rid,lang)
 except Exception:
  return InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده کامل درخواست",callback_data=f"panel:req:{rid}")]])

def _service(B,key,lang):
 try:
  import request_language_actions as L
  return L.service_name(key,lang)
 except Exception:return str(key or "-")

async def _show(update,context,B,rid):
 q=update.callback_query; r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
 if not r:
  await q.answer("درخواست پیدا نشد",show_alert=True); raise ApplicationHandlerStop
 if not B.admin(q.from_user.id):
  pid=B.S.get(q.from_user.id,{}).get("partner_id")
  if pid!=r["user_id"]: await q.answer("دسترسی ندارید",show_alert=True); raise ApplicationHandlerStop
 lang=_lang(B,rid); L=__import__("request_language_actions").labels(lang)
 answers=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
 status=STATUS.get(lang,STATUS["fa"]).get(str(r["status"]),str(r["status"] or "-"))
 lines=[L["details"],"",f"{L['tracking']}: {r['tracking_code']}",f"{L['service']}: {_service(B,r['service_key'],lang)}",f"{L['status']}: {status}",f"{L['amount']}: {int(r['amount'] or 0):,} Toman",f"{L['payment']}: {r['payment_status']}"]
 if r["payment_method"]: lines.append(f"{L['method']}: {r['payment_method']}")
 if r["created_at"]: lines.append(f"{L['time']}: {r['created_at']}")
 lines += ["",L["info"]]
 visible=0
 for a in answers:
  value=str(a["answer"] or "").strip(); has_file=bool(a["file_id"])
  if not value and not has_file: continue
  label=_label(a["field_key"],lang)
  lines.append(f"{label}: {value}" if value else f"{label}: {L['files']}"); visible+=1
 if not visible: lines.append(L["none"])
 await q.message.reply_text("\n".join(lines),reply_markup=_buttons(rid,lang))
 for a in answers:
  fid=a["file_id"]
  if not fid: continue
  caption=_label(a["field_key"],lang)
  try:
   if str(a["field_key"] or "").startswith("file_"): await q.message.reply_document(document=fid,caption=caption)
   else: await q.message.reply_photo(photo=fid,caption=caption)
  except Exception:
   try: await q.message.reply_document(document=fid,caption=caption)
   except Exception: log.exception("request attachment delivery failed: request=%s field=%s",rid,a["field_key"])
 raise ApplicationHandlerStop

async def _callback(update,context,B):
 q=update.callback_query; data=str(q.data or "")
 if not data.startswith("panel:req:"): return
 try: rid=int(data.rsplit(":",1)[1])
 except Exception: await q.answer("Invalid request",show_alert=True); raise ApplicationHandlerStop
 await q.answer(); await _show(update,context,B,rid)

def install(app,B):
 if getattr(B,"_telegram_request_details_fix",False): return
 app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B),pattern=r"^panel:req:"),group=-120)
 B._telegram_request_details_fix=True
