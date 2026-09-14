"""Global Rubika language consistency layer.

The core Rubika flow already stores STATE[uid]['lang'], but several legacy
routers build Persian keyboards/messages directly. This layer localizes those
outgoing labels at the final send boundary, so the selected language is used
consistently without duplicating every legacy handler.
"""
import re

_LANGS = {"fa", "en", "ar"}

_LABELS = {
    "➕ شارژ حساب": {"en":"➕ Top up account", "ar":"➕ شحن الحساب"},
    "🔎 پیگیری کد": {"en":"🔎 Track code", "ar":"🔎 متابعة الرمز"},
    "📋 سوابق": {"en":"📋 History", "ar":"📋 السجل"},
    "💰 موجودی": {"en":"💰 Balance", "ar":"💰 الرصيد"},
    "🏛 حل مشکل سامانه دولت من": {"en":"🏛 Government access issue", "ar":"🏛 مشكلة الدخول إلى الخدمات الحكومية"},
    "✉️ تیکت به مدیریت": {"en":"✉️ Contact management", "ar":"✉️ مراسلة الإدارة"},
    "👥 کاربران": {"en":"👥 Users", "ar":"👥 المستخدمون"},
    "🤝 همکاران": {"en":"🤝 Partners", "ar":"🤝 الشركاء"},
    "📋 درخواست‌ها": {"en":"📋 Requests", "ar":"📋 الطلبات"},
    "💰 شارژ و پرداخت‌ها": {"en":"💰 Top-ups & payments", "ar":"💰 الشحن والمدفوعات"},
    "🟢/🔴 خدمات ایرانی": {"en":"🟢/🔴 Iranian services", "ar":"🟢/🔴 خدمات الإيرانيين"},
    "💳 پرداخت‌های مشتری": {"en":"💳 Customer payments", "ar":"💳 مدفوعات العملاء"},
    "💰 قیمت خدمات": {"en":"💰 Service prices", "ar":"💰 أسعار الخدمات"},
    "📝 تغییر متن‌ها": {"en":"📝 Edit texts", "ar":"📝 تعديل النصوص"},
    "🤖 مدیریت پیام‌رسان‌ها": {"en":"🤖 Messenger management", "ar":"🤖 إدارة تطبيقات المراسلة"},
    "👤 مدیران": {"en":"👤 Administrators", "ar":"👤 المديرون"},
    "📊 گزارش‌ها": {"en":"📊 Reports", "ar":"📊 التقارير"},
    "🎫 تیکت‌ها": {"en":"🎫 Tickets", "ar":"🎫 التذاكر"},
    "📎 فایل‌های درخواست‌ها": {"en":"📎 Request files", "ar":"📎 ملفات الطلبات"},
    "🔄 همگام‌سازی": {"en":"🔄 Synchronize", "ar":"🔄 مزامنة"},
    "📈 قیمت ویژه همکار خاص": {"en":"📈 Special partner pricing", "ar":"📈 أسعار خاصة لشريك محدد"},
    "📞 پشتیبانی": {"en":"📞 Support", "ar":"📞 الدعم"},
    "⚙️ تنظیمات پایه": {"en":"⚙️ Basic settings", "ar":"⚙️ الإعدادات الأساسية"},
    "🪪 فیدای غیر حضوری": {"en":"🪪 FIDA non-in-person", "ar":"🪪 خدمة فيدا عن بُعد"},
    "🖨 خدمات چاپ": {"en":"🖨 Printing", "ar":"🖨 خدمات الطباعة"},
    "🏛 حل مشکل ورود اتباع دولت من": {"en":"🏛 Government access issue", "ar":"🏛 مشكلة الدخول إلى خدمات الحكومة"},
    "🎫 پیگیری": {"en":"🎫 Tracking", "ar":"🎫 متابعة"},
    "📱 خدمات سیم کارت": {"en":"📱 SIM services", "ar":"📱 خدمات شريحة SIM"},
    "📝 آزمون غربالگری و پیگیری": {"en":"📝 Screening & follow-up", "ar":"📝 الفحص والمتابعة"},
    "💰 کیف پول من": {"en":"💰 My wallet", "ar":"💰 محفظتي"},
    "👥 پنل همکاران": {"en":"👥 Partner panel", "ar":"👥 لوحة الشركاء"},
    "📞 تماس با ما": {"en":"📞 Contact us", "ar":"📞 اتصل بنا"},
    "🔄 شروع مجدد": {"en":"🔄 Start again", "ar":"🔄 بدء من جديد"},
    "❌ انصراف": {"en":"❌ Cancel", "ar":"❌ إلغاء"},
    "✅ تأیید": {"en":"✅ Confirm", "ar":"✅ تأكيد"},
    "⬅️ منوی اصلی": {"en":"⬅️ Main menu", "ar":"⬅️ القائمة الرئيسية"},
    "➕ شارژ": {"en":"➕ Top up", "ar":"➕ شحن"},
}

_TEXTS = {
    "❌ عملیات لغو شد.": {"en":"❌ Operation cancelled.", "ar":"❌ تم إلغاء العملية."},
    "🔄 شروع مجدد": {"en":"🔄 Start again", "ar":"🔄 بدء من جديد"},
    "⏳ آزمون غربالگری فعلاً غیرفعال است.": {"en":"⏳ The screening test is currently unavailable.", "ar":"⏳ اختبار الفحص غير متاح حالياً."},
    "🇮🇷 منوی خدمات ایرانی:": {"en":"🇮🇷 Iranian services:", "ar":"🇮🇷 خدمات الإيرانيين:"},
    "❌ اعتبار کافی نیست. لطفاً ابتدا حساب را شارژ کنید.": {"en":"❌ Insufficient balance. Please top up first.", "ar":"❌ الرصيد غير كافٍ. يرجى شحن الحساب أولاً."},
}


def _lang_for_chat(rb, chat):
    chat = str(chat or "")
    for uid, st in rb.STATE.items():
        if str(st.get("chat_id", "")) == chat:
            return st.get("lang", "fa")
    # Most Rubika states do not persist chat_id; recent handlers commonly use
    # uid == chat_id. Prefer an exact state key when available.
    st = rb.STATE.get(chat)
    return st.get("lang", "fa") if isinstance(st, dict) else "fa"


def _localize_label(label, language):
    label = str(label)
    if language == "fa":
        return label
    item = _LABELS.get(label)
    if item:
        return item.get(language, label)
    return label


def _localize_rows(rows, language):
    out = []
    for row in rows or []:
        fixed = []
        for item in row or []:
            if isinstance(item, dict):
                d = dict(item)
                if "button_text" in d:
                    d["button_text"] = _localize_label(d["button_text"], language)
                fixed.append(d)
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                fixed.append((str(item[0]), _localize_label(item[1], language)))
            else:
                fixed.append(item)
        out.append(fixed)
    return out


def _localize_text(text, language):
    if language == "fa":
        return text
    s = str(text)
    if s in _TEXTS:
        return _TEXTS[s].get(language, s)
    return s


def install(rb):
    if getattr(rb, "_netyar_global_language_installed", False):
        return
    original_send = rb.send

    def localized_send(chat, text, rows=None):
        language = _lang_for_chat(rb, chat)
        return original_send(chat, _localize_text(text, language), _localize_rows(rows, language) if rows else rows)

    rb.send = localized_send
    rb._netyar_global_language_installed = True
