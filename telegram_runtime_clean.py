"""Canonical Telegram runtime.

There is exactly one Telegram Application builder in the project. Feature
modules are installed once during build; polling remains exclusively owned by
server.py.
"""
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters
import bot as B
log = logging.getLogger("netyar.telegram_runtime")

def _diagnostic(update, context):
    try:
        if update.message is not None:
            log.info("Telegram update: id=%s user=%s text=%r", update.update_id, getattr(update.effective_user, "id", None), update.message.text)
        elif update.callback_query is not None:
            log.info("Telegram callback: id=%s user=%s data=%r", update.update_id, getattr(update.callback_query.from_user, "id", None), update.callback_query.data)
    except Exception:
        log.exception("Telegram diagnostic failed")

async def _start(update, context):
    user=update.effective_user
    if update.message is None or user is None:return
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("Could not persist Telegram user")
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","lang","status") if k in old}
    await update.message.reply_text("سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))

def _install_features(app):
    import telegram_business_features as F
    F.install(app,B)
    import telegram_admin_plus as A
    app.add_handler(CallbackQueryHandler(lambda u,c:A._callback(u,c,B),pattern=r'^adm:'),group=-20)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:A._text(u,c,B)),group=-19)
    import partner_pricing as P
    P.install_telegram(app,B)
    import telegram_service_pricing as SP
    SP.install(app,B)
    log.info("Telegram business/admin/pricing layers installed")

def build():
    token=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip() or os.getenv("TELEGRAM_TOKEN","").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build()
    app.add_handler(TypeHandler(Update,_diagnostic),group=-100)
    _install_features(app)
    app.add_handler(CommandHandler(["start","srart"],_start),group=0)
    app.add_handler(CommandHandler("addpartner",B.addpartner),group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),B.admin_command),group=0)
    app.add_handler(CallbackQueryHandler(B.langcb,pattern=r'^lang:'),group=0)
    app.add_handler(CallbackQueryHandler(B.statuscb,pattern=r'^st:'),group=0)
    app.add_handler(CallbackQueryHandler(B.admin_cb,pattern=r'^(tu|pay|req|admin):'),group=0)
    try:
        from final_ui_flow_patch import _ui_callback
        app.add_handler(CallbackQueryHandler(_ui_callback,pattern=r'^ui:'),group=0)
    except Exception:log.exception("ui callback unavailable; core Telegram remains active")
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,B.media),group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,B.router),group=1)
    log.info("Canonical Telegram handlers installed")
    return app
