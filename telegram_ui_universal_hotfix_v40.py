"""Universal ui2 callback hotfix v40.

Installed before legacy ui2 owners. Normalizes labels that were present in
older partner menus and dispatches every known user/partner option through the
canonical UI dispatcher. This prevents the generic 'option not executed'
recovery from swallowing valid buttons.
"""
import inspect
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.ui_universal_v40")

ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق",
    "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت",
    "✉️ ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "📝 ثبت شکایت": "📝 ثبت شکایت مشتریان",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 فیدای غیر حضوری",
}

KNOWN = {
    "➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من", "📋 سوابق", "🔎 پیگیری کد",
    "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ", "💰 موجودی", "🎫 تیکت به مدیریت",
    "💬 ارتباط با مدیریت", "📱 خدمات سیم کارت", "📱 حل مشکل سیم کارت ایرانسل",
    "🚪 خروج از پنل", "❌ انصراف", "👥 پنل همکاران", "💰 کیف پول من",
    "🎫 پیگیری", "📞 تماس با ما", "📝 ثبت شکایت مشتریان", "🔄 شروع مجدد",
}


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
