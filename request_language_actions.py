"""Persist the user's selected language on each request and localize manager UX."""
import logging
log = logging.getLogger("netyar.request_language")

LABELS = {
    "fa": {"new":"🆕 درخواست جدید","details":"📋 جزئیات کامل درخواست","tracking":"🎫 کد پیگیری","service":"🧾 خدمت","status":"📌 وضعیت","amount":"💰 مبلغ","payment":"💳 وضعیت پرداخت","method":"💵 روش پرداخت","time":"🕐 زمان ثبت","info":"📋 اطلاعات ثبت‌شده","files":"📎 فایل پیوست دارد","none":"• اطلاعات تکمیلی ثبت نشده است.","ask":"📨 درخواست کد از همکار","resend":"📤 آوردن درخواست به آخر چت","view":"🔎 مشاهده کامل درخواست","review":"⏳ در حال بررسی","done":"✅ انجام شد","reject":"❌ رد درخواست","reply":"✉️ پاسخ به مشترک","captcha":"🔐 کد تصویر","captcha_hint":"📷 تصویر امنیتی را ارسال کنید و کدی را که روی تصویر می‌بینید وارد کنید."},
    "en": {"new":"🆕 New Request","details":"📋 Full Request Details","tracking":"🎫 Tracking Code","service":"🧾 Service","status":"📌 Status","amount":"💰 Amount","payment":"💳 Payment Status","method":"💵 Payment Method","time":"🕐 Created At","info":"📋 Submitted Information","files":"📎 Attachment included","none":"• No additional information was submitted.","ask":"📨 Request Code from Partner","resend":"📤 Bring Request to Chat","view":"🔎 View Full Request","review":"⏳ Under Review","done":"✅ Completed","reject":"❌ Reject Request","reply":"✉️ Reply to Customer","captcha":"🔐 Image Code","captcha_hint":"📷 Send the security image, then enter the code shown in the image."},
    "ar": {"new":"🆕 طلب جديد","details":"📋 تفاصيل الطلب كاملة","tracking":"🎫 رمز التتبع","service":"🧾 الخدمة","status":"📌 الحالة","amount":"💰 المبلغ","payment":"💳 حالة الدفع","method":"💵 طريقة الدفع","time":"🕐 وقت التسجيل","info":"📋 المعلومات المسجلة","files":"📎 يوجد ملف مرفق","none":"• لم يتم تسجيل معلومات إضافية.","ask":"📨 طلب الرمز من الشريك","resend":"📤 إحضار الطلب إلى آخر المحادثة","view":"🔎 عرض الطلب الكامل","review":"⏳ قيد المراجعة","done":"✅ تم الإنجاز","reject":"❌ رفض الطلب","reply":"✉️ الرد على المشترك","captcha":"🔐 رمز الصورة","captcha_hint":"📷 أرسل صورة الأمان ثم أدخل الرمز الظاهر في الصورة."},
}
SERVICE = {
    "fa":{"fida":"🪪 فیدای غیر حضوری","print":"🖨 خدمات چاپ","government":"🏛 حل مشکل ورود اتباع سامانه دولت من","sim_card":"📱 خدمات سیم‌کارت"},
    "en":{"fida":"🪪 Remote FIDA","print":"🖨 Printing Services","government":"🏛 Government My Portal Login Issue","sim_card":"📱 SIM Card Services"},
    "ar":{"fida":"🪪 فيدا عن بُعد","print":"🖨 خدمات الطباعة","government":"🏛 حل مشكلة الدخول إلى بوابة الحكومة","sim_card":"📱 خدمات شرائح الهاتف"},
}

def normalize_lang(value):
    value=str(value or "fa").lower().strip(); return value if value in LABELS else "fa"
def labels(lang): return LABELS[normalize_lang(lang)]
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
    try:
        import rubika_v2 as R
        for st in getattr(R,"STATE",{}).values():
            if st.get("lang") in LABELS and (str(st.get("partner"))==str(owner) or str(st.get("user_id"))==str(owner)):
                return normalize_lang(st.get("lang"))
    except Exception: pass
    return "fa"

def _patch_create_request(db):
    if getattr(db,"_netyar_request_language_create",False): return
    original=db.create_request
    def create_request(user_id,service_key,platform,amount,*args,**kwargs):
        result=original(user_id,service_key,platform,amount,*args,**kwargs)
        try:
            db.conn.execute("UPDATE requests SET language=? WHERE id=?",(_language_from_states(user_id),int(result[0]))); db.conn.commit()
        except Exception: log.exception("failed to persist request language")
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

def admin_markup(rid,lang):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    l=labels(lang)
    return InlineKeyboardMarkup([[InlineKeyboardButton(l["ask"],callback_data=f"panel:askcode:{rid}")],[InlineKeyboardButton(l["resend"],callback_data=f"panel:resend:{rid}")],[InlineKeyboardButton(l["view"],callback_data=f"panel:req:{rid}")],[InlineKeyboardButton(l["review"],callback_data=f"panel:review:{rid}"),InlineKeyboardButton(l["done"],callback_data=f"panel:approve:{rid}")],[InlineKeyboardButton(l["reject"],callback_data=f"panel:reject:{rid}"),InlineKeyboardButton(l["reply"],callback_data=f"req:r:{rid}")]])
