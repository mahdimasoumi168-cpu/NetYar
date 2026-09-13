"""Final night-shift partner logout guard.
Handles the Reply-keyboard logout before legacy/off-hours handlers can intercept it.
"""
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
        # Only consume the button when the user is actually in a partner session.
        if st.get("mode") not in {"partner", "final_partner_chat", "partner_exit_choice"} and not st.get("partner_id"):
            return
        lang = st.get("lang", "fa")
        status = st.get("status") or st.get("citizenship") or "foreign"
        # Remove every authentication/session key so night shift never trusts an old login.
        for key in ("partner", "partner_id", "partner_phone", "partner_active", "partner", "step",
                    "night_phone", "night_partner_id", "final_chat_admin", "final_chat_partner_id",
                    "final_chat_rid", "ticket_partner_id", "ticket_request_id"):
            st.pop(key, None)
        st.update(mode=None, partner_logged_out=True, status=status, citizenship=status, lang=lang)
        try:
            await msg.reply_text(
                "✅ با موفقیت از پنل همکاران خارج شدید.\n\nبرای ورود دوباره، دکمه «👥 پنل همکاران» را انتخاب کنید.",
                reply_markup=B.main(uid),
            )
        finally:
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, logout), group=-40000)
    B._night_logout_final_installed = True
    return True
