"""Final Telegram integration guard.

This is intentionally the last Telegram layer.  It does not implement a second
menu; it only rebinds the canonical UI owners after legacy installers and makes
restart deterministic before every other customer router.
"""
import logging
from telegram import Update
from telegram.ext import TypeHandler, MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.final_integration")
RESTART_TEXTS = {"🔄 شروع مجدد", "شروع مجدد", "/restart"}


def install(app, B):
    if getattr(B, "_final_integration_guard_v1", False):
        return

    import telegram_ui_policy_v2 as UI
    import telegram_final_partner_panel as PP

    # Reassert the canonical owners after every older compatibility layer.
    B.main = lambda uid: UI.inline(UI._main_rows(B, uid), B, uid)
    B.cancel_kb = lambda lang="fa": UI.inline([[UI.CANCEL]], B)
    B.partner_kb = lambda lang="fa": PP._partner_keyboard(UI, B, UI._uid() or 0)

    async def restart_message(update, context):
        msg = getattr(update, "effective_message", None)
        if not msg:
            return
        text = str(getattr(msg, "text", "") or "").strip()
        if text not in RESTART_TEXTS:
            return
        try:
            await B.start(update, context)
        except Exception:
            log.exception("universal restart failed")
            try:
                await msg.reply_text(
                    "❌ شروع مجدد با خطا مواجه شد. لطفاً دوباره تلاش کنید."
                )
            except Exception:
                pass
        raise ApplicationHandlerStop

    async def restart_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or str(q.data or "") != "off:restart":
            return
        try:
            await q.answer()
            # Use the exact same canonical /start reset as a real /start.
            await B.start(
                type("RestartUpdate", (), {
                    "effective_user": q.from_user,
                    "effective_message": q.message,
                    "message": q.message,
                })(),
                context,
            )
        except Exception:
            log.exception("off-hours callback restart failed")
            try:
                await q.message.reply_text("❌ شروع مجدد انجام نشد. لطفاً دوباره تلاش کنید.")
            except Exception:
                pass
        raise ApplicationHandlerStop

    # Run before the absolute off-hours gate, so restart is always available.
    app.add_handler(CallbackQueryHandler(restart_callback, pattern=r"^off:restart$"), group=-30000000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, restart_message), group=-29999999)

    B._final_integration_guard_v1 = True
    log.info("Final Telegram integration guard installed")
