"""Reset stale Telegram conversational sessions on the next user action."""
import os
import time
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop


DEFAULT_IDLE_SECONDS = 5 * 60


def install(app, B):
    if getattr(B, "_idle_session_reset_installed", False):
        return

    try:
        idle_seconds = max(60, int(os.getenv("SESSION_IDLE_SECONDS", str(DEFAULT_IDLE_SECONDS))))
    except Exception:
        idle_seconds = DEFAULT_IDLE_SECONDS

    async def text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not msg.text:
            return

        uid = user.id
        now = time.monotonic()
        st = B.S.setdefault(uid, {})
        previous = st.get("_last_activity")

        # Always refresh activity so an active conversation never expires.
        st["_last_activity"] = now

        # If the user comes back after inactivity, the next button/text starts
        # from the public main menu instead of continuing an old data-entry step.
        if previous is None:
            return
        try:
            stale = (now - float(previous)) >= idle_seconds
        except Exception:
            stale = False
        if not stale:
            return

        lang = st.get("lang", "fa")
        await msg.reply_text(
            "⏰ به دلیل چند دقیقه عدم فعالیت، عملیات قبلی بسته شد.\n\n🏠 به صفحه اصلی برگشتید.\nلطفاً گزینه موردنظر را دوباره انتخاب کنید.",
            reply_markup=B.main(uid),
        )
        raise ApplicationHandlerStop

    # Run before all conversational routers so stale modes cannot consume
    # the first action after the timeout.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-1000000)
    B._idle_session_reset_installed = True
