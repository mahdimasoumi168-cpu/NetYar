"""Final Telegram callback/text owner v43.

Owns Telegram ui2 callbacks before legacy handlers. It resolves the label,
then sends it to the stable callback router instead of the legacy UI dispatcher.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.ui_absolute_v43")
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SITE_URL = "https://netyarmohajer.sizpay.ir"
TRUST_LABELS = {"🛡 اعتماد", "🛡️ اعتماد"}
ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق",
    "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت",
    "📝 ثبت شکایت": "📝 ثبت شکایت مشتریان",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 فیدای غیر حضوری",
}
MENU_TEXTS = {
    "➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من", "🎫 درخواست‌های من",
    "📋 سوابق", "🔎 پیگیری کد", "💰 موجودی", "💰 کیف پول من",
    "🪪 فیدای غیر حضوری", "🪪 حل مشکل ورود اتباع دولت من", "🖨 خدمات چاپ",
    "📱 خدمات سیم کارت", "📱 حل مشکل سیم کارت ایرانسل", "🎫 تیکت به مدیریت",
    "📨 ارسال پیام به مدیریت", "✉️ ارسال تیکت به مدیریت", "💬 ارتباط با مدیریت",
    "📝 ثبت شکایت", "📝 ثبت شکایت مشتریان", "🚪 خروج از پنل", "❌ انصراف",
    "🔄 شروع مجدد", "🔄 شروع دوباره", "👥 پنل همکاران", "🛠 پنل مدیریت بات",
}

def _label_from_markup(q, data):
    try:
        for row in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
            for button in row or []:
                if str(getattr(button, "callback_data", "") or "") == data:
                    return str(getattr(button, "text", "") or "").strip()
    except Exception:
        log.exception("v43 markup label recovery failed")
    return ""

async def _trust(q):
    await q.answer()
    await q.message.reply_text(
        "🛡 نماد اعتماد الکترونیکی\n\n"
        "🏢 نام کسب‌وکار: نت یار مهاجر\n"
        "🔤 نام لاتین: NetYareMohajer\n"
        "🌐 دامنه: netyarmohajer.sizpay.ir\n"
        "☎️ تلفن: 03135674350\n"
        "📧 ایمیل: netyaremohajer@gmail.com",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
            [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
            [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی", callback_data="iranian:back")],
        ]), disable_web_page_preview=True)

async def _iranian_back(q, B):
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})
    st["status"] = "iranian"
    st["mode"] = None
    try:
        import telegram_final_iranian_menu_v38 as I
        markup = I._keyboard(B, uid)
    except Exception:
        markup = B.main(uid)
    await q.answer()
    await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=markup)

async def _dispatch_label(update, context, B, label):
    """Dispatch ui2 labels through the independent stable callback router."""
    label = ALIASES.get(str(label or "").strip(), str(label or "").strip())
    if label in TRUST_LABELS:
        return await _trust(update.callback_query)
    from telegram_stable_callback import handle
    result = handle(update, context, B, label)
    if hasattr(result, "__await__"):
        return await result
    return result

async def install_callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q:
        return
    data = str(getattr(q, "data", "") or "")
    if data == "enamad:trust":
        await _trust(q); raise ApplicationHandlerStop
    if data == "iranian:back":
        await _iranian_back(q, B); raise ApplicationHandlerStop
    if not data.startswith("ui2:"):
        return
    token = data[4:]
    label = ""
    try:
        row = B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)).fetchone()
        if row:
            try:
                owner = row["user_id"]; label = str(row["label"] or "").strip(); lang = row["lang"]; status = row["status"]
            except Exception:
                owner, label, lang, status = row[0], str(row[1] or "").strip(), row[2], row[3]
            if owner and str(owner) != str(q.from_user.id):
                await q.answer("این دکمه متعلق به حساب دیگری است.", show_alert=True); raise ApplicationHandlerStop
            st = B.S.setdefault(q.from_user.id, {})
            if lang: st["lang"] = lang
            if status: st["status"] = status
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("v43 ui2 lookup failed")
    if not label:
        label = _label_from_markup(q, data)
    label = ALIASES.get(label, label)
    if not label:
        await q.answer("این دکمه منقضی شده است؛ لطفاً منو را دوباره باز کنید.", show_alert=True); raise ApplicationHandlerStop
    try:
        await _dispatch_label(update, context, B, label)
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("v43 stable callback failed label=%r data=%r", label, data)
        uid = q.from_user.id; st = B.S.setdefault(uid, {})
        try:
            markup = B.partner_kb(st.get("lang", "fa")) if st.get("partner_id") and st.get("partner_active", True) else B.main(uid)
            await q.message.reply_text("❌ خطای داخلی در اجرای این گزینه؛ وضعیت فعلی شما حفظ شد.", reply_markup=markup)
        except Exception:
            log.exception("v43 recovery failed")
        raise ApplicationHandlerStop

async def install_text(update, context, B):
    msg = getattr(update, "message", None)
    if not msg: return
    text = str(getattr(msg, "text", "") or "").strip()
    if text in TRUST_LABELS:
        await msg.reply_text(
            "🛡 نماد اعتماد الکترونیکی\n\n🏢 نام کسب‌وکار: نت یار مهاجر\n🔤 نام لاتین: NetYareMohajer\n🌐 دامنه: netyarmohajer.sizpay.ir\n☎️ تلفن: 03135674350\n📧 ایمیل: netyaremohajer@gmail.com",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
                [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
            ]), disable_web_page_preview=True)
        raise ApplicationHandlerStop
    if text not in MENU_TEXTS: return
    try:
        await B.router(update, context)
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("v43 text dispatch failed label=%r", text)
        await msg.reply_text("❌ خطای داخلی در اجرای این گزینه؛ وضعیت فعلی شما حفظ شد.")
    raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, "_absolute_ui_owner_v43", False): return
    app.add_handler(CallbackQueryHandler(install_callback), group=-6000000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, install_text), group=-6000001)
    B._absolute_ui_owner_v43 = True
    log.info("ABSOLUTE Telegram callback/text owner v43 installed")
