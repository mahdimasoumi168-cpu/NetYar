"""Persist request language and exact Telegram requester identity."""
import logging,time
log=logging.getLogger("netyar.request_language")
LABELS={"fa":{"new":"🆕 درخواست جدید","details":"📋 اطلاعات کامل درخواست","tracking":"🎫 کد پیگیری","service":"🧾 خدمت","status":"📌 وضعیت","amount":"💰 مبلغ","payment":"💳 وضعیت پرداخت","method":"💵 روش پرداخت","time":"🕐 زمان ثبت","info":"📋 اطلاعات ثبت‌شده","ask":"📨 درخواست کد از حساب ثبت‌کننده","resend":"📤 انتقال به آخر چت","view":"🔎 مشاهده اطلاعات کامل","review":"⏳ در حال بررسی","done":"✅ انجام شد","reject":"❌ رد درخواست","reply":"✉️ پاسخ به مشترک","back":"⬅️ بازگشت به پنل مدیریت"},"en":{"new":"🆕 New Request","details":"📋 Full Request Information","tracking":"🎫 Tracking Code","service":"🧾 Service","status":"📌 Status","amount":"💰 Amount","payment":"💳 Payment Status","method":"💵 Payment Method","time":"🕐 Created At","info":"📋 Submitted Information","ask":"📨 Request Code from Requesting Account","resend":"📤 Move to End of Chat","view":"🔎 View Full Information","review":"⏳ Under Review","done":"✅ Completed","reject":"❌ Reject Request","reply":"✉️ Reply to Customer","back":"⬅️ Back to Admin Panel"},"ar":{"new":"🆕 طلب جديد","details":"📋 معلومات الطلب كاملة","tracking":"🎫 رمز التتبع","service":"🧾 الخدمة","status":"📌 الحالة","amount":"💳 المبلغ","payment":"💳 حالة الدفع","method":"💵 طريقة الدفع","time":"🕐 وقت التسجيل","info":"📋 المعلومات المسجلة","ask":"📨 طلب الرمز من الحساب الذي سجّل الطلب","resend":"📤 نقل إلى آخر المحادثة","view":"🔎 عرض المعلومات الكاملة","review":"⏳ قيد المراجعة","done":"✅ تم الإنجاز","reject":"❌ رفض الطلب","reply":"✉️ الرد على المشترك","back":"⬅️ العودة إلى لوحة الإدارة"}}
FIELD_LABELS={"fa":{"phone":"📱 شماره موبایل مشترک","mobile":"📱 شماره موبایل مشترک","customer_phone":"📱 شماره موبایل مشترک","dob":"🎂 تاریخ تولد مشترک","birth_date":"🎂 تاریخ تولد مشترک","unique_id":"🆔 شناسه یکتای مشترک","unique_code":"🆔 شناسه یکتای مشترک","special_id":"🔖 شناسه اختصاصی مشترک","special_code":"🔖 شناسه اختصاصی مشترک","family_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","household_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","passport":"🛂 شماره پاسپورت مشترک","passport_number":"🛂 شماره پاسپورت مشترک","doc_type":"🪪 نوع مدرک","name":"👤 نام و نام خانوادگی","full_name":"👤 نام و نام خانوادگی","user_id":"🆔 شناسه حساب ثبت‌کننده","platform":"🌐 بستر ثبت درخواست","updated_at":"🕐 آخرین بروزرسانی"},"en":{"phone":"📱 Customer Mobile","mobile":"📱 Customer Mobile","customer_phone":"📱 Customer Mobile","dob":"🎂 Date of Birth","birth_date":"🎂 Date of Birth","unique_id":"🆔 Unique ID","unique_code":"🆔 Unique ID","special_id":"🔖 Special ID","special_code":"🔖 Special ID","family_code":"👨‍👩‍👧‍👦 Family Code","household_code":"👨‍👩‍👧‍👦 Family Code","passport":"🛂 Passport Number","passport_number":"🛂 Passport Number","doc_type":"🪪 Document Type","name":"👤 Full Name","full_name":"👤 Full Name","user_id":"🆔 Request Account ID","platform":"🌐 Request Platform","updated_at":"🕐 Last Updated"},"ar":{"phone":"📱 هاتف المشترك","mobile":"📱 هاتف المشترك","customer_phone":"📱 هاتف المشترك","dob":"🎂 تاريخ الميلاد","birth_date":"🎂 تاريخ الميلاد","unique_id":"🆔 المعرّف الفريد","unique_code":"🆔 المعرّف الفريد","special_id":"🔖 المعرّف الخاص","special_code":"🔖 المعرّف الخاص","family_code":"👨‍👩‍👧‍👦 رمز الأسرة","household_code":"👨‍👩‍👧‍👦 رمز الأسرة","passport":"🛂 رقم جواز السفر","passport_number":"🛂 رقم جواز السفر","doc_type":"🪪 نوع الوثيقة","name":"👤 الاسم الكامل","full_name":"👤 الاسم الكامل","user_id":"🆔 معرّف الحساب المسجّل","platform":"🌐 منصة الطلب","updated_at":"🕐 آخر تحديث"}}
SERVICE={"fa":{"fida":"🪪 فیدای غیر حضوری","print":"🖨 خدمات چاپ","government":"🏛 حل مشکل ورود اتباع سامانه دولت من","sim_card":"📱 خدمات سیم‌کارت"},"en":{"fida":"🪪 Remote FIDA","print":"🖨 Printing Services","government":"🏛 Government My Portal Login Issue","sim_card":"📱 SIM Card Services"},"ar":{"fida":"🪪 فيدا عن بُعد","print":"🖨 خدمات الطباعة","government":"🏛 حل مشكلة الدخول إلى بوابة الحكومة","sim_card":"📱 خدمات شرائح الهاتف"}}
def normalize_lang(v):v=str(v or "fa").lower().strip();return v if v in LABELS else "fa"
def labels(lang):return LABELS[normalize_lang(lang)]
def field_label(key,lang):return FIELD_LABELS.get(normalize_lang(lang),FIELD_LABELS["fa"]).get(str(key),f"📋 {str(key).replace('_',' ')}")
def service_name(key,lang):return SERVICE.get(normalize_lang(lang),SERVICE["fa"]).get(str(key),str(key or "-"))
def _ensure_column(db):
 cols={str(r[1]) for r in db.conn.execute("PRAGMA table_info(requests)").fetchall()}
 if "language" not in cols:db.conn.execute("ALTER TABLE requests ADD COLUMN language TEXT DEFAULT 'fa'");db.conn.commit()
def _touch(app,B):
 if getattr(B,"_request_identity_tracker",False):return
 from telegram.ext import TypeHandler
 async def h(update,context):
  try:
   uid=getattr(getattr(update,"effective_user",None),"id",None)
   if uid is not None:
    st=B.S.setdefault(uid,{});st["telegram_chat_id"]=str(uid);st["telegram_last_seen"]=time.time()
  except Exception:pass
 app.add_handler(TypeHandler(object,h),group=-10000);B._request_identity_tracker=True
def _best_chat(owner,db):
 try:
  import bot as B;c=[]
  for raw,st in getattr(B,"S",{}).items():
   if not isinstance(st,dict):continue
   if str(st.get("partner_id"))==str(owner) or str(st.get("user_id"))==str(owner):
    uid=str(st.get("telegram_chat_id") or raw).strip()
    if uid.lstrip("-").isdigit():c.append((float(st.get("telegram_last_seen") or 0),uid))
  if c:return max(c,key=lambda x:x[0])[1]
  r=db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram' LIMIT 1",(owner,)).fetchone();return str(r["external_id"]).strip() if r else ""
 except Exception:return ""
def _lang(owner):
 try:
  import bot as B;best=(0,"fa")
  for st in getattr(B,"S",{}).values():
   if isinstance(st,dict) and (str(st.get("partner_id"))==str(owner) or str(st.get("user_id"))==str(owner)):
    seen=float(st.get("telegram_last_seen") or 0);lang=normalize_lang(st.get("lang","fa"))
    if seen>=best[0]:best=(seen,lang)
  return best[1]
 except Exception:return "fa"
def _patch(db):
 if getattr(db,"_netyar_request_identity_create",False):return
 old=db.create_request
 def create_request(user_id,service_key,platform,amount,*a,**kw):
  out=old(user_id,service_key,platform,amount,*a,**kw)
  try:
   rid=int(out[0]);db.conn.execute("UPDATE requests SET language=? WHERE id=?",(_lang(user_id),rid))
   if str(platform).lower()=="telegram":db.set_setting(f"request_chat_{rid}",_best_chat(user_id,db));db.set_setting(f"request_created_by_{rid}",_best_chat(user_id,db))
   db.conn.commit()
  except Exception:log.exception("request identity persistence failed")
  return out
 db.create_request=create_request;db._netyar_request_identity_create=True
def install(app=None,B=None,*a,**kw):
 try:
  import core;_ensure_column(core.db);_patch(core.db)
  if app is not None and B is not None:_touch(app,B)
 except Exception:log.exception("request identity layer installation failed")
def request_language(db,rid):
 try:r=db.conn.execute("SELECT language FROM requests WHERE id=?",(rid,)).fetchone();return normalize_lang(r["language"] if r else "fa")
 except Exception:return "fa"
def request_chat(db,rid):return str(db.setting(f"request_chat_{rid}","") or "").strip()
def admin_markup(rid,lang,include_view=True):
 from telegram import InlineKeyboardMarkup,InlineKeyboardButton
 l=labels(lang);rows=[]
 if include_view:rows += [[InlineKeyboardButton(l["ask"],callback_data=f"panel:askcode:{rid}")],[InlineKeyboardButton(l["resend"],callback_data=f"panel:resend:{rid}")],[InlineKeyboardButton(l["view"],callback_data=f"panel:req:{rid}")]]
 else:rows += [[InlineKeyboardButton(l["resend"],callback_data=f"panel:resend:{rid}")],[InlineKeyboardButton(l["ask"],callback_data=f"panel:askcode:{rid}")]]
 rows += [[InlineKeyboardButton(l["review"],callback_data=f"panel:review:{rid}"),InlineKeyboardButton(l["done"],callback_data=f"panel:approve:{rid}")],[InlineKeyboardButton(l["reject"],callback_data=f"panel:reject:{rid}"),InlineKeyboardButton(l["reply"],callback_data=f"req:r:{rid}")],[InlineKeyboardButton(l["back"],callback_data="adm:menu")]]
 return InlineKeyboardMarkup(rows)
