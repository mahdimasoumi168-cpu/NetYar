"""Final Telegram production bootstrap.

Builds the PTB application directly from the stable bot handlers instead of
using the long chain of legacy B.build monkey-patches. Telegram is polling-only.
"""
import logging
import os

log = logging.getLogger("netyar.telegram_final")


def build():
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )
    import bot as B

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing")

    app = Application.builder().token(token).build()

    # Register the canonical handlers exactly once, in deterministic order.
    app.add_handler(CommandHandler("start", B.start), group=0)
    app.add_handler(CommandHandler("addpartner", B.addpartner), group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"), B.admin_command), group=0)
    app.add_handler(CallbackQueryHandler(B.langcb, pattern=r"^lang:"), group=0)
    app.add_handler(CallbackQueryHandler(B.statuscb, pattern=r"^st:"), group=0)
    app.add_handler(CallbackQueryHandler(B.admin_cb, pattern=r"^(tu|pay|req|admin):"), group=0)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, B.media), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, B.router), group=1)

    log.info("Telegram canonical handlers installed")
    return app


def install():
    import telegram_runtime
    telegram_runtime.build = build
    log.info("Telegram production final bootstrap installed")
