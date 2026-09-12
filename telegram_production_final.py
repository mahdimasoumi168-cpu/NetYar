"""Final Telegram production bootstrap.

Telegram is polling-only and owns its authoritative handlers here. This
module intentionally avoids the legacy build/handler monkey-patch chain.
"""
import logging
import os

log = logging.getLogger("netyar.telegram_final")


async def _authoritative_start(update, context):
    """Minimal, independent /start entry point for production."""
    import bot as B
    try:
        log.info(
            "Telegram /start received: user=%s chat=%s",
            getattr(getattr(update, "effective_user", None), "id", None),
            getattr(getattr(update, "effective_chat", None), "id", None),
        )
        await B.start(update, context)
    except Exception:
        log.exception("Telegram /start handler failed")
        msg = getattr(update, "message", None)
        if msg is not None:
            try:
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                await msg.reply_text(
                    "سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
                            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
                            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar"),
                        ]
                    ]),
                )
            except Exception:
                log.exception("Telegram /start fallback reply failed")


async def _telegram_update_diagnostic(update, context):
    """Log incoming Telegram updates without changing their routing."""
    try:
        if getattr(update, "message", None) is not None:
            log.info(
                "Telegram update received: update_id=%s user=%s text=%r",
                getattr(update, "update_id", None),
                getattr(getattr(update, "effective_user", None), "id", None),
                getattr(update.message, "text", None),
            )
        elif getattr(update, "callback_query", None) is not None:
            log.info(
                "Telegram callback received: update_id=%s user=%s data=%r",
                getattr(update, "update_id", None),
                getattr(getattr(update.callback_query, "from_user", None), "id", None),
                getattr(update.callback_query, "data", None),
            )
    except Exception:
        log.exception("Telegram update diagnostic failed")


def build():
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        TypeHandler,
        filters,
    )
    from telegram import Update
    import bot as B

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing")

    app = Application.builder().token(token).build()
    app.add_handler(TypeHandler(Update, _telegram_update_diagnostic), group=-10)

    # /start is authoritative. Also accept the common /srart typo so a
    # mistyped command cannot make the bot appear dead to the user.
    app.add_handler(CommandHandler(["start", "srart"], _authoritative_start), group=0)
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
