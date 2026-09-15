"""Final Telegram partner logout guard.

Logout is a real authentication reset. During off-hours it never starts a new
credential flow automatically; the user must explicitly choose the partner
panel, while ordinary customer input remains blocked by the canonical gate.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

LOGOUTS = {"🚪 خروج از پنل", "🚪 خروج", "Exit panel", "🚪 Exit partner panel"}


def _closed_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])


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
        if (
            st.get("mode") not in {"partner", "final_partner_chat", "partner_exit_choice"}
            and not st.get("partner_id")
        ):
            return

        lang = st.get("lang", "fa")
        status = st.get("status") or st.get("citizenship") or "foreign"

        # Complete authentication/session reset. Keep only public identity
        # fields; do not leave partner credentials or routing state behind.
        for key in (
            "partner", "partner_id", "partner_phone", "partner_active", "step",
            "night_phone", "night_partner_id", "final_chat_admin", "final_chat_partner",
            "final_chat_partner_id", "final_chat_rid", "ticket_partner_id", "ticket_request_id",
            "reply_target", "reply_request_id",
        ):
            st.pop(key, None)
        st.update(
            mode=None,
            partner_logged_out=True,
            status=status,
            citizenship=status,
            lang=lang,
        )

        # Use the same canonical Tehran clock as the off-hours gate. The helper
        # is installed by telegram_offhours_api_fix before this module runs.
        try:
            from telegram_offhours_partner_gate_v2 import is_open
            night = not bool(is_open(B))
        except Exception:
            night = False

        if night:
            # Do NOT put the user into night_phone/night_pass here. They must
            # explicitly press "پنل همکاران" before any partner authentication.
            await msg.reply_text(
                "✅ با موفقیت از پنل همکاران خارج شدید.\n\n"
                "🔒 دسترسی قبلی کاملاً بسته شد و ورود خودکار غیرفعال شد.\n\n"
                "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n"
                "برای ورود دوباره، فقط از «👥 پنل همکاران» اقدام کنید.",
                reply_markup=_closed_markup(),
            )
        else:
            await msg.reply_text(
                "✅ با موفقیت از پنل همکاران خارج شدید.\n\n"
                "برای ورود دوباره، از «👥 پنل همکاران» وارد شوید.",
                reply_markup=B.main(uid),
            )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, logout), group=-40000)
    B._night_logout_final_installed = True
    return True
