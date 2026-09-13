"""Final night-shift partner logout guard.
Handles the Reply-keyboard logout before legacy/off-hours handlers can intercept it.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

LOGOUTS = {"🚪 خروج از پنل", "🚪 خروج", "🚪 Exit panel", "🚪 Exit partner panel"}


def install(app, B):
    if getattr(B, "_night_logout_final_installed", False):
        return True

    async def logout(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or (msg.text or "").strip() not in LOGOUTS:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") not in {"partner", "final_partner_chat", "partner_exit_choice"} and not st.get("partner_id"):
            return
        lang = st.get("lang", "fa")
        status = st.get("status") or st.get("citizenship") or "foreign"
        for key in (
            "partner", "partner_id", "partner_phone", "partner_active", "step",
            "night_phone", "night_partner_id", "final_chat_admin", "final_chat_partner",
            "final_chat_partner_id", "final_chat_rid", "ticket_partner_id", "ticket_request_id",
            "reply_target", "reply_request_id", "partner_logged_out",
        ):
            st.pop(key, None)
        st.update(mode=None, partner_logged_out=True, status=status, citizenship=status, lang=lang)

        # During the night shift, logout must completely terminate authentication
        # and start a fresh credential flow instead of showing the public menu.
        try:
            from telegram_offhours_partner_gate_v2 import is_open
            night = not is_open()
        except Exception:
            night = False

        if night:
            st["mode"] = "night_phone"
            st["step"] = "night_phone"
            await msg.reply_text(
                "✅ با موفقیت از پنل همکاران خارج شدید.\n\n"
                "🔒 دسترسی قبلی کاملاً بسته شد و اطلاعات ورود قبلی دیگر معتبر نیست.\n\n"
                "🌙 برای ورود دوباره در شیفت شب، شماره موبایل اختصاصی همکار را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ انصراف", callback_data="off:restart")]
                ]),
            )
        else:
            await msg.reply_text(
                "✅ با موفقیت از پنل همکاران خارج شدید.\n\nبرای ورود دوباره، از «👥 پنل همکاران» وارد شوید.",
                reply_markup=B.main(uid),
            )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, logout), group=-40000)
    B._night_logout_final_installed = True
    return True
