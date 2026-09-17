"""Universal ui2 callback hotfix v40.

Installed before legacy ui2 owners. Normalizes labels that were present in
older menus and dispatches known options through the canonical UI dispatcher.
It also owns critical menu-only actions such as eNAMAD trust so they cannot
fall through to the generic "option not executed" recovery.
"""
import inspect
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.ui_universal_v40")

TRUST_LABELS = {"🛡 اعتماد", "🛡️ اعتماد"}
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SITE_URL = "https://netyarmohajer.sizpay.ir"

ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق",
    "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت",
    "✉️ ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "📝 ثبت شکایت": "📝 ثبت شکایت مشتریان",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 فیدای غیر حضوری",
}

KNOWN = {
    "➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من", "🏛 خدمات ایرانی", "📋 سوابق", "🔎 پیگیری کد",
    "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ", "💰 موجودی", "🎫 تیکت به مدیریت",
    "💬 ارتباط با مدیریت", "📱 خدمات سیم کارت", "📱 حل مشکل سیم کارت ایرانسل",
    "🚪 خروج از پنل", "❌ انصراف", "👥 پنل همکاران", "💰 کیف پول من",
    "🎫 پیگیری", "📞 تماس با ما", "📝 ثبت شکایت مشتریان", "🔄 شروع مجدد",
    "🛡 اعتماد", "🛡️ اعتماد",
}


def _trust_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
        [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
        [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی", callback_data="iranian:back")],
    ])


def _trust_message():
    return (
        "🛡 نماد اعتماد الکترونیکی\n\n"
        "🏢 نام کسب‌وکار: نت یار مهاجر\n"
        "🔤 نام لاتین: NetYareMohajer\n"
        "🌐 دامنه: netyarmohajer.sizpay.ir\n"
        "☎️ تلفن: 03135674350\n"
        "📧 ایمیل: netyaremohajer@gmail.com"
    )


def install(app, B):
    if getattr(B, "_ui_universal_hotfix_v40", False):
        return

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("ui2:"):
            return
        token = str(q.data)[4:]
        row = B.db.conn.execute(
            "SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)
        ).fetchone()
        if row and row["user_id"] and str(row["user_id"]) != str(q.from_user.id):
            await q.answer("این دکمه متعلق به حساب دیگری است.", show_alert=True)
            raise ApplicationHandlerStop
        label = str(row["label"] or "").strip() if row else ""
        if not label:
            await q.answer("این دکمه دیگر معتبر نیست؛ لطفاً منو را دوباره باز کنید.", show_alert=True)
            raise ApplicationHandlerStop
        label = ALIASES.get(label, label)
        st = B.S.setdefault(q.from_user.id, {})
        if row and row["lang"]:
            st["lang"] = row["lang"]
        if row and row["status"]:
            st["status"] = row["status"]
        try:
            await q.answer()
        except Exception:
            pass

        # Critical menu action: never send eNAMAD through the generic router.
        if label in TRUST_LABELS:
            await q.message.reply_text(
                _trust_message(),
                reply_markup=_trust_markup(),
                disable_web_page_preview=True,
            )
            raise ApplicationHandlerStop

        # Iranian services is a menu navigation action, not a service router.
        if label == "🏛 خدمات ایرانی":
            st["status"] = "iranian"
            st["mode"] = None
            try:
                import telegram_final_iranian_menu_v38 as I
                await q.message.reply_text(
                    "🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:",
                    reply_markup=I._keyboard(B, q.from_user.id),
                )
            except Exception:
                log.exception("iranian menu navigation failed")
                await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nلطفاً گزینه موردنظر را انتخاب کنید.", reply_markup=B.main(q.from_user.id))
            raise ApplicationHandlerStop

        try:
            import telegram_ui_policy_v2 as UI
            fake = UI._fake(update, label)
            result = UI._dispatch(update, context, B, label)
            if inspect.isawaitable(result):
                await result
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("universal ui2 dispatch failed label=%r", label)
            if label in KNOWN:
                await q.message.reply_text(
                    "❌ اجرای این گزینه با خطای داخلی مواجه شد؛ وضعیت و پنل شما حفظ شد. لطفاً دوباره همان گزینه را بزنید.",
                    reply_markup=B.partner_kb(st.get("lang", "fa")) if st.get("partner_id") and st.get("partner_active") else B.main(q.from_user.id),
                )
            else:
                await q.message.reply_text("❌ این گزینه در نسخه فعلی تعریف نشده است.", reply_markup=B.main(q.from_user.id))
            raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-3000000)
    B._ui_universal_hotfix_v40 = True
    log.info("Universal ui2 callback hotfix v40 installed")
