"""Canonical Telegram runtime.

There is exactly one Telegram Application builder in the project.
Feature code lives in bot.py; this module only registers the authoritative
handlers. It never starts polling and never patches the lifecycle.
"""
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

import bot as B

log = logging.getLogger("netyar.telegram_runtime")


def _diagnostic(update, context):
    try:
        if update.message is not None:
            log.info(
                "Telegram update: id=%s user=%s text=%r",
                update.update_id,
                getattr(update.effective_user, "id", None),
                update.message.text,
            )
        elif update.callback_query is not None:
            log.info(
                "Telegram callback: id=%s user=%s data=%r",
                update.update_id,
                getattr(update.callback_query.from_user, "id", None),
                update.callback_query.data,
            )
    except Exception:
        log.exception("Telegram diagnostic failed")


async def _start(update, context):
    """Authoritative /start: reset only the conversational state."""
    user = update.effective_user
    message = update.message
    if message is None:
        return
    uid = user.id
    try:
        B.db.user("telegram", uid, user.username, user.full_name)
    except Exception:
        log.exception("Could not persist Telegram user")
    B.S[uid] = {}
    await message.reply_text(
        "سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
                InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar"),
            ]
        ]),
    )


def build():
    """Build exactly one Application; polling belongs to server.py."""
    token = (
        os.getenv("BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_TOKEN", "").strip()
    )
    if not token:
        raise RuntimeError("Telegram bot token is missing")

    app = Application.builder().token(token).build()

    # Diagnostics never stop or consume an update.
    app.add_handler(TypeHandler(Update, _diagnostic), group=-100)

    # One authoritative startup handler.
    app.add_handler(CommandHandler(["start", "srart"], _start), group=0)
    app.add_handler(CommandHandler("addpartner", B.addpartner), group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"), B.admin_command), group=0)

    # Entry screens and admin callbacks.
    app.add_handler(CallbackQueryHandler(B.langcb, pattern=r"^lang:"), group=0)
    app.add_handler(CallbackQueryHandler(B.statuscb, pattern=r"^st:"), group=0)
    app.add_handler(CallbackQueryHandler(B.admin_cb, pattern=r"^(tu|pay|req|admin):"), group=0)

    # UI callback layer is optional: if unavailable, the core bot still starts.
    try:
        from final_ui_flow_patch import _ui_callback
        app.add_handler(CallbackQueryHandler(_ui_callback, pattern=r"^ui:"), group=0)
        log.info("Telegram ui:* callback handler installed")
    except Exception:
        log.exception("ui:* callback handler unavailable; core Telegram remains active")

    # Media must run before the generic text router, while both remain in one
    # predictable handler group.
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, B.media), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, B.router), group=1)

    log.info("Canonical Telegram handlers installed")
    return app
