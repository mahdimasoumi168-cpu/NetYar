"""Persist request language and provide localized admin request controls/details."""
import logging
log = logging.getLogger("netyar.request_language")

LABELS = {
    "fa": {"new":"🆕 درخواست جدید","details":"📋 جزئیات کامل درخواست","tracking":"🎫 کد پیگیری","service":"🧾 خدمت","status":"📌 وضعیت","amount":"💰 مبلغ","payment":"💳 وضعیت پرداخت","method":"💵 روش پرداخت","time":"🕐 زمان ثبت","info":"📋 اطلاعات ثبت‌شده","files":"📎 فایل پیوست دارد","none":"• اطلاعات تکمیلی ثبت نشده است.","ask":"📨 درخواست کد از همکار","resend":"📤 انتقال به آخر چت","view":"🔎 مشاهده اطلاعات کامل","review":"⏳ در حال بررسی","done":"✅ انجام شد","reject":"❌ رد درخواست","reply":"✉️ پاسخ به مشترک","back":"⬅️ بازگشت به پنل مدیریت"},
    "en": {"new":"🆕 New Request","details":"📋 Full Request Details","tracking":"🎫 Tracking Code","service":"🧾 Service","status":"📌 Status","amount":"💰 Amount","payment":"💳 Payment Status","method":"💵 Payment Method","time":"🕐 Created At","info":"📋 Submitted Information","files":"📎 Attachment included","none":"• No additional information was submitted.","ask":"📨 Request Code from Partner","resend":"📤 Move to End of Chat","view":"🔎 View Full Information","review":"⏳ Under Review","done":"✅ Completed","reject":"❌ Reject Request","reply":"✉️ Reply to Customer","back":"⬅️ Back to Admin Panel"},
    "ar": {"new":"🆕 طلب جديد","details":"📋 تفاصيل الطلب كاملة","tracking":"🎫 رمز التتبع","service":"🧾 الخدمة","status":"📌 الحالة","amount":"💳 المبلغ","payment":"💳 حالة الدفع","method":"💵 طريقة الدفع","time":"🕐 وقت التسجيل","info":"📋 المعلومات المسجلة","files":"📎 يوجد ملف مرفق","none":"• لم يتم تسجيل معلومات إضافية.","ask":"📨 طلب الرمز من الشريك","resend":"📤 نقل إلى آخر المحادثة","view":"🔎 عرض المعلومات الكاملة","review":"⏳ قيد المراجعة","done":"✅ تم الإنجاز","reject":"❌ رفض الطلب","reply":"✉️ الرد على المشترك","back":"⬅️ العودة إلى لوحة الإدارة"},
}
SERVICE = {
    "fa":{"fida":"🪪 فیدای غیر حضوری","print":"🖨 خدمات چاپ","government":"🏛 حل مشکل ورود اتباع سامانه دولت من","sim_card":"📱 خدمات سیم‌کارت"},
    "en":{"fida":"🪪 Remote FIDA","print":"🖨 Printing Services","government":"🏛 Government My Portal Login Issue","sim_card":"📱 SIM Card Services"},
    "ar":{"fida":"🪪 فيدا عن بُعد","print":"🖨 خدمات الطباعة","government":"🏛 حل مشكلة الدخول إلى بوابة الحكومة","sim_card":"📱 خدمات شرائح الهاتف"},
}
FIELD_LABELS = {
    "fa":{"phone":"📱 شماره موبایل مشترک","mobile":"📱 شماره موبایل مشترک","amount":"💰 مبلغ","payment_status":"💳 وضعیت پرداخت","payment_method":"💵 روش پرداخت","doc_type":"🪪 نوع مدرک","unique_id":"🆔 شناسه یکتا","special_id":"🔖 شناسه اختصاصی","family_code":"👨‍👩‍👧‍👦 کد خانوار","postal_code":"📮 کد پستی","passport":"🛂 شماره/اطلاعات پاسپورت","gov_passport":"🛂 اطلاعات پاسپورت","name":"👤 نام و نام خانوادگی","first_name":"👤 نام","last_name":"👤 نام خانوادگی","national_code":"🆔 کد ملی","address":"🏠 نشانی","document":"📎 مدرک","user_id":"👤 شناسه ثبت‌کننده","platform":"🌐 بستر ثبت درخواست","updated_at":"🕐 آخرین بروزرسانی"},
    "en":{"phone":"📱 Customer Mobile","mobile":"📱 Customer Mobile","amount":"💰 Amount","payment_status":"💳 Payment Status","payment_method":"💵 Payment Method","doc_type":"🪪 Document Type","unique_id":"🆔 Unique ID","special_id":"🔖 Special ID","family_code":"👨‍👩‍👧‍👦 Family Code","postal_code":"📮 Postal Code","passport":"🛂 Passport Number/Information","gov_passport":"🛂 Passport Information","name":"👤 Full Name","first_name":"👤 First Name","last_name":"👤 Last Name","national_code":"🆔 National ID","address":"🏠 Address","document":"📎 Document","user_id":"👤 Requester ID","platform":"🌐 Request Platform","updated_at":"🕐 Last Updated"},
    "ar":{"phone":"📱 هاتف المشترك","mobile":"📱 هاتف المشترك","amount":"💰 المبلغ","payment_status":"💳 حالة الدفع","payment_method":"💵 طريقة الدفع","doc_type":"🪪 نوع الوثيقة","unique_id":"🆔 المعرّف الفريد","special_id":"🔖 المعرّف الخاص","family_code":"👨‍👩‍👧‍👦 رمز الأسرة","postal_code":"📮 الرمز البريدي","passport":"🛂 رقم/معلومات جواز السفر","gov_passport":"🛂 معلومات جواز السفر","name":"👤 الاسم الكامل","first_name":"👤 الاسم","last_name":"👤 اسم العائلة","national_code":"🆔 الرقم الوطني","address":"🏠 العنوان","document":"📎 الوثيقة","user_id":"👤 معرّف صاحب الطلب","platform":"🌐 منصة تسجيل الطلب","updated_at":"🕐 آخر تحديث"},
}

def normalize_lang(value):
    value=str(value or "fa").lower().strip(); return value if value in LABELS else "fa"
def labels(lang): return LABELS[normalize_lang(lang)]
def field_label(key,lang): return FIELD_LABELS.get(normalize_lang(lang),FIELD_LABELS["fa"]).get(str(key),f"📋 {str(key).replace('_',' ')}")
def service_name(key,lang): return SERVICE.get(normalize_lang(lang),SERVICE["fa"]).get(str(key),str(key or "-"))

def _ensure_column(db):
    cols={str(r[1]) for r in db.conn.execute("PRAGMA table_info(requests)").fetchall()}
    if "language" not in cols:
        db.conn.execute("ALTER TABLE requests ADD COLUMN language TEXT DEFAULT 'fa'"); db.conn.commit()

def _language_from_states(owner):
    try:
        import bot as B
        for st in getattr(B,"S",{}).values():
            if st.get("lang") in LABELS and (str(st.get("partner_id"))==str(owner) or str(st.get("user_id"))==str(owner)):
                return normalize_lang(st.get("lang"))
    except Exception: pass
    return "fa"

def _telegram_chat_from_states(owner):
    try:
        import bot as B
        for raw_uid,st in getattr(B,"S",{}).items():
            if not isinstance(st,dict): continue
            if str(st.get("partner_id"))==str(owner) or str(st.get("user_id"))==str(owner):
                uid=str(raw_uid).strip()
                if uid.lstrip("-").isdigit(): return uid
    except Exception: pass
    return ""

def _patch_create_request(db):
    if getattr(db,"_netyar_request_language_create",False): return
    original=db.create_request
    def create_request(user_id,service_key,platform,amount,*args,**kwargs):
        result=original(user_id,service_key,platform,amount,*args,**kwargs)
        try:
            rid=int(result[0]); lang=_language_from_states(user_id)
            db.conn.execute("UPDATE requests SET language=? WHERE id=?",(lang,rid))
            # Persist the exact Telegram chat that created the request. This is
            # stronger than resolving a partner from phone/id later and prevents
            # a code request from being sent to the wrong linked account.
            if str(platform).lower()=="telegram":
                chat=_telegram_chat_from_states(user_id)
                if chat: db.set_setting(f"request_chat_{rid}",chat)
            db.conn.commit()
        except Exception: log.exception("failed to persist request language/chat")
        return result
    db.create_request=create_request; db._netyar_request_language_create=True

def install(*_args,**_kwargs):
    try:
        import core
        _ensure_column(core.db); _patch_create_request(core.db)
    except Exception: log.exception("request language layer installation failed")

def request_language(db,rid):
    try:
        r=db.conn.execute("SELECT language FROM requests WHERE id=?",(rid,)).fetchone()
        return normalize_lang(r["language"] if r else "fa")
    except Exception: return "fa"

def admin_markup(rid,lang,include_view=True):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    l=labels(lang); rows=[]
    if include_view:
        rows.append([InlineKeyboardButton(l["ask"],callback_data=f"panel:askcode:{rid}")])
        rows.append([InlineKeyboardButton(l["resend"],callback_data=f"panel:resend:{rid}")])
        rows.append([InlineKeyboardButton(l["view"],callback_data=f"panel:req:{rid}")])
    else:
        rows.append([InlineKeyboardButton(l["resend"],callback_data=f"panel:resend:{rid}")])
        rows.append([InlineKeyboardButton(l["ask"],callback_data=f"panel:askcode:{rid}")])
    rows += [[InlineKeyboardButton(l["review"],callback_data=f"panel:review:{rid}"),InlineKeyboardButton(l["done"],callback_data=f"panel:approve:{rid}")],[InlineKeyboardButton(l["reject"],callback_data=f"panel:reject:{rid}"),InlineKeyboardButton(l["reply"],callback_data=f"req:r:{rid}")]]
    rows.append([InlineKeyboardButton(l["back"],callback_data="adm:menu")])
    return InlineKeyboardMarkup(rows)
