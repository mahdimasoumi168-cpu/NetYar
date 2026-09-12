"""Canonical Telegram runtime with one Application and deterministic feature installation."""
import logging,os
from telegram import InlineKeyboardButton,InlineKeyboardMarkup,Update
from telegram.ext import Application,CallbackQueryHandler,CommandHandler,MessageHandler,TypeHandler,filters
import bot as B
log=logging.getLogger("netyar.telegram_runtime")

def _diagnostic(update,context):
    try:
        if update.message is not None:log.info("Telegram update id=%s user=%s text=%r",update.update_id,getattr(update.effective_user,"id",None),update.message.text)
        elif update.callback_query is not None:log.info("Telegram callback id=%s user=%s data=%r",update.update_id,getattr(update.effective_user,"id",None),update.callback_query.data)
    except Exception:log.exception("Telegram diagnostic failed")
async def _start(update,context):
    user=update.effective_user
    if not update.message or not user:return
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","lang","status","phone") if k in old}
    await update.message.reply_text("سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))
def _install_features(app):
    import telegram_business_features as F;F.install(app,B)
    import telegram_ui_policy_v2 as UI;UI.install(app,B)
    import telegram_admin_plus as A
    app.add_handler(CallbackQueryHandler(lambda u,c:A._callback(u,c,B),pattern=r'^adm:'),group=-20)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:A._text(u,c,B)),group=-19)
    try:
        import telegram_admin_entry as AE;AE.install(app,B)
    except Exception:log.exception("admin entry unavailable")
    import telegram_government_flow_v2 as G;G.install(app,B)
    import partner_pricing as P;P.install_telegram(app,B)
    import telegram_service_pricing as SP;SP.install(app,B)
    import telegram_night_shift_v2 as N;N.install(app,B)
    import telegram_request_control_v2 as RC;RC.install(app,B)
    log.info("Telegram feature layers installed")
def build():
    token=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip() or os.getenv("TELEGRAM_TOKEN","").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build();app.add_handler(TypeHandler(Update,_diagnostic),group=-1000);_install_features(app)
    app.add_handler(CommandHandler(["start","srart"],_start),group=0);app.add_handler(CommandHandler("addpartner",B.addpartner),group=0);app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),B.admin_command),group=0)
    app.add_handler(CallbackQueryHandler(B.langcb,pattern=r'^lang:'),group=0);app.add_handler(CallbackQueryHandler(B.statuscb,pattern=r'^st:'),group=0);app.add_handler(CallbackQueryHandler(B.admin_cb,pattern=r'^(tu|pay|req|admin):'),group=0)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,B.media),group=1);app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,B.router),group=1)
    log.info("Canonical Telegram handlers installed");return app
