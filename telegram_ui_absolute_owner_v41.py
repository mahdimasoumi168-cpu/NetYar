"""Absolute ui2 callback owner v41.

This is the final safety-net owner for every Telegram ui2 callback. It is
registered in an extremely early handler group so legacy callback handlers
cannot swallow valid buttons and show the old generic fallback message.
"""
import inspect
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.ui_absolute_v41")

TRUST = {"🛡 اعتماد", "🛡️ اعتماد"}
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SITE_URL = "https://netyarmohajer.sizpay.ir"
ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق",
    "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت",
    "✉️ ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "📝 ثبت شکایت": "📝 ثبت شکایت مشتریان",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 حل مشکل ورود اتباع دولت من",
}


def _trust_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
        [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
        [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی", callback_data="iranian:back")],
    ])


def _call(result):
    return inspect.isawaitable(result)


def install(app, B):
    if getattr(B, "_absolute_ui_owner_v41", False):
        return

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("ui2:"):
            return
        uid = q.from_user.id
        token = str(q.data)[4:]
        try:
            row = B.db.conn.execute(
                "SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)
            ).fetchone()
        except Exception:
            row = None
        if row and row["user_id"] and str(row["user_id"]) != str(uid):
            await q.answer("این دکمه متعلق به حساب دیگری است.", show_alert=True)
            raise ApplicationHandlerStop
        label = str(row["label"] or "").strip() if row else ""
        if not label:
            try:
                for buttons in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
                    for button in buttons or []:
                        if getattr(button, "callback_data", None) == q.data:
                            label = str(getattr(button, "text", "") or "").strip()
                            break
                    if label:
                        break
            except Exception:
                pass
        if not label:
            await q.answer("این دکمه منقضی شده است؛ منو را دوباره باز کنید.", show_alert=True)
            raise ApplicationHandlerStop
        label = ALIASES.get(label, label)
        st = B.S.setdefault(uid, {})
        if row and row["lang"]:
            st["lang"] = row["lang"]
        if row and row["status"]:
            st["status"] = row["status"]
        try:
            await q.answer()
        except Exception:
            pass

        if label in TRUST:
            await q.message.reply_text(
                "🛡 نماد اعتماد الکترونیکی\n\n"
                "🏢 نام کسب‌وکار: نت یار مهاجر\n"
                "🔤 نام لاتین: NetYareMohajer\n"
                "🌐 دامنه: netyarmohajer.sizpay.ir\n"
                "☎️ تلفن: 03135674350\n"
                "📧 ایمیل: netyaremohajer@gmail.com",
                reply_markup=_trust_markup(),
                disable_web_page_preview=True,
            )
            raise ApplicationHandlerStop

        if label == "🏛 خدمات ایرانی":
            st["status"] = "iranian"
            st["mode"] = None
            try:
                import telegram_final_iranian_menu_v38 as I
                markup = I._keyboard(B, uid)
            except Exception:
                markup = B.main(uid)
            await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=markup)
            raise ApplicationHandlerStop

        try:
            import telegram_ui_policy_v2 as UI
            fake = UI._fake(update, label)
            result = UI._dispatch(update, context, B, label)
            if _call(result):
                await result
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("v41 ui2 dispatch failed label=%r", label)
            # Retry through the absolute partner dispatcher for partner labels.
            try:
                import telegram_absolute_callback_hardening_v30 as V30
                result = V30._dispatch(update, context, B, label)
                if _call(result):
                    await result
                raise ApplicationHandlerStop
            except ApplicationHandlerStop:
                raise
            except Exception:
                log.exception("v41 secondary dispatch failed label=%r", label)
                if st.get("partner_id") and st.get("partner_active", True) and not st.get("partner_logged_out"):
                    markup = B.partner_kb(st.get("lang", "fa"))
                else:
                    markup = B.main(uid)
                await q.message.reply_text(
                    "❌ خطای موقت در اجرای گزینه؛ وضعیت شما حفظ شد. لطفاً همان گزینه را دوباره بزنید.",
                    reply_markup=markup,
                )
                raise ApplicationHandlerStop

    # Must be earlier than every legacy ui2 handler, including v30.
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-999999999)
    B._absolute_ui_owner_v41 = True
    log.info("ABSOLUTE Telegram ui2 callback owner v41 installed")
