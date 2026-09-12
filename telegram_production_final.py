"""Final Telegram production bootstrap.

Telegram is polling-only and owns its authoritative handlers here.
This module is the final handler registration point for Telegram.
"""
import logging
import os

log = logging.getLogger("netyar.telegram_final")


async def _authoritative_start(update, context):
    """Always show the exact first screen: language selection only."""
    import bot as B
    try:
        user = getattr(update, "effective_user", None)
        msg = getattr(update, "message", None)
        if msg is None:
            return
        uid = getattr(user, "id", None)
        if uid is not None:
            try:
                B.db.user("telegram", uid, getattr(user, "username", None), getattr(user, "full_name", None))
            except Exception:
                log.exception("Telegram user initialization failed")
            B.S[uid] = {}
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await msg.reply_text(
            "سلام و خوش آمدید 🌷\n"
            "لطفاً زبان را انتخاب کنید / Choose your language / اختر اللغة:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
                InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar"),
            ]]),
        )
    except Exception:
        log.exception("Telegram /start handler failed")


async def _telegram_update_diagnostic(update, context):
    try:
        if getattr(update, "message", None) is not None:
            log.info("Telegram update received: update_id=%s user=%s text=%r", getattr(update, "update_id", None), getattr(getattr(update, "effective_user", None), "id", None), getattr(update.message, "text", None))
        elif getattr(update, "callback_query", None) is not None:
            log.info("Telegram callback received: update_id=%s user=%s data=%r", getattr(update, "update_id", None), getattr(getattr(update.callback_query, "from_user", None), "id", None), getattr(update.callback_query, "data", None))
    except Exception:
        log.exception("Telegram update diagnostic failed")


def build():
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters
    from telegram import Update
    import bot as B

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing")

    app = Application.builder().token(token).build()
    app.add_handler(TypeHandler(Update, _telegram_update_diagnostic), group=-10)

    app.add_handler(CommandHandler(["start", "srart"], _authoritative_start), group=0)
    app.add_handler(CommandHandler("addpartner", B.addpartner), group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"), B.admin_command), group=0)

    # Direct callbacks used by the initial screens and admin actions.
    app.add_handler(CallbackQueryHandler(B.langcb, pattern=r"^lang:"), group=0)
    app.add_handler(CallbackQueryHandler(B.statuscb, pattern=r"^st:"), group=0)
    app.add_handler(CallbackQueryHandler(B.admin_cb, pattern=r"^(tu|pay|req|admin):"), group=0)

    # IMPORTANT: final_ui_flow_patch converts Telegram menus into ui:* callbacks.
    # The previous production bootstrap accidentally replaced its build() and
    # dropped this handler, which made most buttons appear dead.
    try:
        from final_ui_flow_patch import _ui_callback
        app.add_handler(CallbackQueryHandler(_ui_callback, pattern=r"^ui:"), group=0)
        log.info("Telegram UI callback handler installed")
    except Exception:
        log.exception("Telegram UI callback handler could not be installed")

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, B.media), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, B.router), group=1)

    log.info("Telegram canonical handlers installed")
    return app


def install():
    import telegram_runtime
    telegram_runtime.build = build
    log.info("Telegram production final bootstrap installed")
