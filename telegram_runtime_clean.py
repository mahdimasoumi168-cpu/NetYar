"""Canonical Telegram runtime with one Application and deterministic feature installation."""
import logging, os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters
import bot as B
log=logging.getLogger("netyar.telegram_runtime")


def _diagnostic(update, context):
    try:
        if update.message is not None:
            log.info("Telegram update id=%s user=%s text=%r", update.update_id, getattr(update.effective_user,"id",None), update.message.text)
        elif update.callback_query is not None:
            log.info("Telegram callback id=%s user=%s data=%r", update.update_id, getattr(update.effective_user,"id",None), update.callback_query.data)
    except Exception:
        log.exception("Telegram diagnostic failed")


async def _start(update, context):
    user=update.effective_user
    if not update.message or not user:return
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","lang","status","phone") if k in old}
    await update.message.reply_text("سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))


def _install_features(app):
    B.start=_start
    import telegram_business_features as F; F.install(app,B)
    import telegram_ui_policy_v2 as UI; UI.install(app,B)
    try:
        import telegram_partner_ui_fix as PUI; PUI.install(app,B)
    except Exception: log.exception("partner UI fix unavailable")
    import telegram_status_ui as SU; SU.install(app,B)
    try:
        import telegram_public_tracking as PT; PT.install(app,B)
    except Exception: log.exception("public tracking unavailable")
    try:
        import telegram_sim_service_v2 as SIM; SIM.install(app,B)
    except Exception: log.exception("SIM service unavailable")
    try:
        import telegram_topup_invoice as TI
        TI.install(B)
        if getattr(B,"_topup_invoice_install_app",None): B._topup_invoice_install_app(app)
    except Exception: log.exception("topup invoice unavailable")

    import telegram_admin_plus as A
    app.add_handler(CallbackQueryHandler(lambda u,c:A._callback(u,c,B),pattern=r'^adm:'),group=-20)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:A._text(u,c,B)),group=-19)
    try:
        import telegram_admin_entry as AE; AE.install(app,B)
    except Exception: log.exception("admin entry unavailable")
    import telegram_government_flow_v2 as G; G.install(app,B)
    try:
        import telegram_government_flow_runtime_fix as GF; GF.install(app,B)
    except Exception: log.exception("government flow runtime fix unavailable")
    import partner_pricing as P; P.install_telegram(app,B)
    import telegram_service_pricing as SP; SP.install(app,B)
    import telegram_night_shift_v2 as N; N.install(app,B)
    import telegram_admin_menu_v2 as AM; AM.install(B)
    import telegram_request_control_v2 as RC; RC.install(app,B)
    try:
        import telegram_legacy_callback_bridge as LCB; LCB.install(app,B)
    except Exception: log.exception("legacy callback bridge unavailable")
    try:
        import telegram_partner_code_reliable as PCR; PCR.install(app,B)
    except Exception: log.exception("partner code handler unavailable")
    try:
        import telegram_request_resend_fa as RFA; RFA.install(app,B)
    except Exception: log.exception("request resend handler unavailable")
    import telegram_access_hardening as AH; AH.install(app,B)
    try:
        import telegram_partner_visibility_fix as PV; PV.install(app,B)
    except Exception: log.exception("partner visibility fix unavailable")
    # telegram_ui_policy_v2 historically wrapped start to send a second
    # "دسترسی سریع" message. The canonical start flow must stay single-shot.
    B.start=_start
    log.info("Telegram feature layers installed")


def build():
    token=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip() or os.getenv("TELEGRAM_TOKEN","").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build()
    app.add_handler(TypeHandler(Update,_diagnostic),group=-1000)
    _install_features(app)
    app.add_handler(CommandHandler(["start","srart"],B.start),group=0)
    app.add_handler(CommandHandler("addpartner",B.addpartner),group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),B.admin_command),group=0)
    app.add_handler(CallbackQueryHandler(B.langcb,pattern=r'^lang:'),group=0)
    app.add_handler(CallbackQueryHandler(B.statuscb,pattern=r'^st:'),group=0)
    app.add_handler(CallbackQueryHandler(B.admin_cb,pattern=r'^(tu|pay|req|admin):'),group=0)
    # Generic B.media/B.router handlers were running after specialized feature
    # handlers and could execute the same action a second time. Feature modules
    # now own their respective message/media states; do not register the legacy
    # catch-all handlers here.
    log.info("Canonical Telegram handlers installed without legacy catch-all router")
    return app
