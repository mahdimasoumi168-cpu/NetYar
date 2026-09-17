"""Universal Telegram callback owner v48.

Single owner for ui2 callbacks. Telegram callback objects are treated as
immutable; runtime state is passed explicitly. The trust entry intentionally
contains only the eNAMAD verification link and no site/payment link.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.universal_owner_v48")
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
TRUST = {"🛡 اعتماد", "🛡️ اعتماد"}
ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق",
    "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت",
    "📝 ثبت شکایت": "📝 ثبت شکایت مشتریان",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 فیدای غیر حضوری",
    "🔵 👥 پنل همکاران": "👥 پنل همکاران",
    "👥 Partner panel": "👥 پنل همکاران",
    "👥 لوحة الشركاء": "👥 پنل همکاران",
    "🛠 پنل مدیریت": "🛠 پنل مدیریت بات",
}
KNOWN = {
    "➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من", "🔎 پیگیری کد", "📋 سوابق",
    "💰 موجودی", "💰 کیف پول من", "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ",
    "🪪 حل مشکل ورود اتباع دولت من", "📱 خدمات سیم کارت", "📱 حل مشکل سیم کارت ایرانسل",
    "🎫 تیکت به مدیریت", "💬 ارتباط با مدیریت", "🚪 خروج از پنل", "❌ انصراف",
    "🔄 شروع مجدد", "🔄 شروع دوباره", "👥 پنل همکاران", "🛠 پنل مدیریت بات",
    "🎫 پیگیری", "📞 تماس با ما", "📝 ثبت شکایت مشتریان",
}

def _label(q, B):
    data = str(getattr(q, "data", "") or "")
    try:
        if data.startswith("ui2:"):
            token = data[4:]
            row = B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)).fetchone()
            if row:
                uid = str(q.from_user.id)
                owner = str(row["user_id"] if hasattr(row, "keys") else row[0])
                if owner and owner != uid:
                    return "__FORBIDDEN__"
                return str(row["label"] if hasattr(row, "keys") else row[1] or "").strip()
    except Exception:
        log.exception("ui2 label lookup failed")
    try:
        for row in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
            for b in row or []:
                if str(getattr(b, "callback_data", "") or "") == data:
                    return str(getattr(b, "text", "") or "").strip()
    except Exception:
        pass
    return ""

async def _trust(q):
    await q.answer()
    await q.message.reply_text(
        "🛡 نماد اعتماد الکترونیکی\n\n"
        "🏢 نام کسب‌وکار: نت یار مهاجر\n"
        "🔤 نام لاتین: NetYareMohajer\n"
        "☎️ تلفن: 03135674350\n"
        "📧 ایمیل: netyaremohajer@gmail.com",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
        ]),
        disable_web_page_preview=True,
    )

async def callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q:
        return
    data = str(getattr(q, "data", "") or "")
    if data == "enamad:trust":
        await _trust(q)
        raise ApplicationHandlerStop
    if data == "iranian:back":
        try:
            import telegram_ui_absolute_owner_v43 as UI
            await UI._iranian_back(q, B)
        except Exception:
            await q.answer()
            await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=B.main(q.from_user.id))
        raise ApplicationHandlerStop
    if not data.startswith("ui2:"):
        return
    raw_label = _label(q, B)
    label = ALIASES.get(raw_label, raw_label)
    if not label:
        return
    if label == "__FORBIDDEN__":
        await q.answer("این دکمه متعلق به حساب دیگری است.", show_alert=True)
        raise ApplicationHandlerStop
    if label in TRUST:
        await _trust(q)
        raise ApplicationHandlerStop
    try:
        await q.answer()
    except Exception:
        pass
    if label in KNOWN:
        try:
            from telegram_stable_callback import handle
            await handle(update, context, B, label)
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("stable route failed label=%r", label)
            uid = q.from_user.id
            st = B.S.setdefault(uid, {})
            if st.get("partner_id") and st.get("partner_active", True):
                await q.message.reply_text("❌ اجرای این گزینه با خطا روبه‌رو شد؛ پنل همکاران شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            else:
                await q.message.reply_text("❌ اجرای این گزینه با خطا روبه‌رو شد. لطفاً دوباره تلاش کنید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop
    try:
        import telegram_ui_policy_v2 as UI
        fn = getattr(UI, "_dispatch", None)
        if fn:
            result = await fn(update, context, B, label)
            if result is not None:
                raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("canonical route failed label=%r", label)
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})
    if st.get("partner_id") and st.get("partner_active", True):
        await q.message.reply_text("⛔ این گزینه در پنل همکاران شناخته نشد؛ پنل شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
    elif st.get("mode"):
        await q.message.reply_text("⛔ این گزینه در مرحله فعلی شناخته نشد؛ مرحله شما حفظ شد.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
    else:
        await q.message.reply_text("⛔ این گزینه شناخته نشد. لطفاً /start را بزنید.", reply_markup=B.main(uid))
    raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, "_universal_callback_owner_v48", False):
        return
    async def _bound(update, context):
        return await callback(update, context, B)
    app.add_handler(CallbackQueryHandler(_bound, pattern=r"^(ui2:|enamad:trust|iranian:back)"), group=-8000000)
    B._universal_callback_owner_v48 = True
    log.info("UNIVERSAL Telegram callback owner v48 installed (no site link)")
