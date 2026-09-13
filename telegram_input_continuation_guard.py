"""Final text-flow firewall for Telegram.

A large legacy codebase can have several MessageHandlers matching the same
text. This guard records an active flow before handlers run and terminates the
update after the active flow had a chance to process it, preventing the common
"error then success" / duplicate-message behavior.
"""
from telegram.ext import ApplicationHandlerStop, MessageHandler, filters


def install(app, B):
    if getattr(B, "_input_continuation_guard", False):
        return

    def _capture(update, context):
        u = update.effective_user
        m = update.effective_message
        if not u or not m:
            return
        st = B.S.setdefault(u.id, {})
        mode = st.get("mode")
        admin_mode = st.get("admin_plus_mode") if B.admin(u.id) else None
        # Only mark actual conversational states. Ordinary menu text must be
        # allowed to reach the normal router.
        if mode or admin_mode:
            st["_continuation_guard_active"] = True
            st["_continuation_guard_mode"] = mode or admin_mode
        else:
            st.pop("_continuation_guard_active", None)
            st.pop("_continuation_guard_mode", None)

    async def _stop(update, context):
        u = update.effective_user
        if not u:
            return
        st = B.S.get(u.id, {})
        if st.pop("_continuation_guard_active", False):
            st.pop("_continuation_guard_mode", None)
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.ALL, _capture), group=-300)
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO, _stop), group=5000)
    B._input_continuation_guard = True
