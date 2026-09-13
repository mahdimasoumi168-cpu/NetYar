"""Canonical Telegram runtime with one Application and deterministic feature installation."""
import logging, os, inspect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters, ApplicationHandlerStop
import bot as B
log=logging.getLogger("netyar.telegram_runtime")
_LANGS={"fa","en","ar"}
_STATUSES={"foreign","iranian"}
async def _safe_call(fn, update, context):
    try:
        result=fn(update,context)
        if inspect.isawaitable(result): return await result
        return result
    except ApplicationHandlerStop: raise
    except Exception: log.exception("Telegram handler failed: %r",fn); return None
async def _diagnostic(update, context):
    try:
        if update.message is not None: log.info("Telegram update id=%s user=%s text=%r",update.update_id,getattr(update.effective_user,"id",None),update.message.text)
        elif update.callback_query is not None: log.info("Telegram callback id=%s user=%s data=%r",update.update_id,getattr(update.effective_user,"id",None),update.callback_query.data)
    except Exception: log.exception("Telegram diagnostic failed")
async def _error_handler(update, context):
    try: log.error("Telegram unhandled error update_id=%s",getattr(update,"update_id",None),exc_info=context.error)
    except Exception: log.exception("Telegram error handler failed")
async def _start(update, context):
    user=update.effective_user
    if not update.message or not user:return
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","lang","status","phone") if k in old}
    text=("👋 سلام!\n\nبه سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\nلطفاً خدمت موردنظر خود را از منوی زیر انتخاب کنید تا در سریع‌ترین زمان راهنمایی شوید.\n\n🚀 بات، کمک یار مهاجر؛ خدماتی برای شما، درآمدی برای همه.\n\nلطفاً زبان را انتخاب کنید.")
    await update.message.reply_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))
async def _lang_select(update,context):
    q=update.callback_query
    if not q:return
    await q.answer();uid=q.from_user.id;lang=str(q.data or "").split(":",1)[-1]
    if lang not in _LANGS:lang="fa"
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","phone") if k in old};B.S[uid]["lang"]=lang
    texts={"fa":"آیا اتباع هستید یا ایرانی؟","en":"Are you a foreign national or Iranian?","ar":"هل أنت أجنبی أم إیرانی؟"}
    labels={"fa":("🪪 اتباع هستم","🇮🇷 ایرانی هستم"),"en":("🪪 Foreign national","🇮🇷 Iranian"),"ar":("🪪 أجنبي","🇮🇷 إيراني")}[lang]
    await q.message.reply_text(texts[lang],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(labels[0],callback_data="startup:foreign"),InlineKeyboardButton(labels[1],callback_data="startup:iranian")]]));raise ApplicationHandlerStop
async def _status_select(update,context):
    q=update.callback_query
    if not q:return
    await q.answer();uid=q.from_user.id;status=str(q.data or "").split(":",1)[-1];st=B.S.setdefault(uid,{})
    if status not in _STATUSES: raise ApplicationHandlerStop
    st["status"]=status;st["citizenship"]=status;st.pop("mode",None);lang=st.get("lang","fa")
    text={"fa":"منوی خدمات کمک یار مهاجر 👇","en":"Mohajer Helper services 👇","ar":"قائمة خدمات المهاجرين 👇"}[lang] if status=="foreign" else {"fa":"🇮🇷 منوی خدمات ایرانی 👇","en":"🇮🇷 Iranian user menu 👇","ar":"🇮🇷 قائمة المستخدم الإيراني 👇"}[lang]
    await q.message.reply_text(text,reply_markup=B.main(uid));raise ApplicationHandlerStop
async def _absolute_startup_callback(update,context):
    q=getattr(update,"callback_query",None)
    if not q:return
    data=str(q.data or "").strip()
    if data in {"lang:fa","lang:en","lang:ar","language:fa","language:en","language:ar"}:
        lang=data.split(":",1)[1];log.info("Telegram startup language callback handled: %r",data);await q.answer();uid=q.from_user.id;old=B.S.get(uid,{})
        B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","phone") if k in old};B.S[uid]["lang"]=lang
        texts={"fa":"آیا اتباع هستید یا ایرانی؟","en":"Are you a foreign national or Iranian؟","ar":"هل أنت أجنبي أم إيراني؟"};labels={"fa":("🪪 اتباع هستم","🇮🇷 ایرانی هستم"),"en":("🪪 Foreign national","🇮🇷 Iranian"),"ar":("🪪 أجنبي","🇮🇷 إيراني")}[lang]
        await q.message.reply_text(texts[lang],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(labels[0],callback_data="startup:foreign"),InlineKeyboardButton(labels[1],callback_data="startup:iranian")]]));raise ApplicationHandlerStop
    if data in {"foreign","iranian","st:foreign","st:iranian","startup:foreign","startup:iranian","status:foreign","status:iranian"}:
        status=data.split(":",1)[1] if ":" in data else data;log.info("Telegram startup citizenship callback handled: %r -> %s",data,status);await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{})
        st["status"]=status;st["citizenship"]=status;st.pop("mode",None);lang=st.get("lang","fa");lang=lang if lang in _LANGS else "fa"
        text={"fa":"منوی خدمات کمک یار مهاجر 👇","en":"Mohajer Helper services 👇","ar":"قائمة خدمات المهاجرين 👇"}[lang] if status=="foreign" else {"fa":"🇮🇷 منوی خدمات ایرانی 👇","en":"🇮🇷 Iranian user menu 👇","ar":"🇮🇷 قائمة المستخدم الإيراني 👇"}[lang]
        await q.message.reply_text(text,reply_markup=B.main(uid));raise ApplicationHandlerStop

def _install_features(app):
    B.start=_start
    try:
        import telegram_startup_button_firewall as SBF;SBF.install(app,B)
    except Exception:log.exception("startup button firewall unavailable")
    import telegram_business_features as F;F.install(app,B)
    import telegram_ui_policy_v2 as UI;UI.install(app,B)
    try:
        import telegram_language_consistency as TLC;TLC.install(B);log.info("Telegram language consistency lock active")
    except Exception:log.exception("Telegram language consistency lock unavailable")
    try:
        import telegram_partner_ui_fix as PUI;PUI.install(app,B)
    except Exception:log.exception("partner UI fix unavailable")
    try:
        import telegram_public_tracking as PT;PT.install(app,B)
    except Exception:log.exception("public tracking unavailable")
    try:
        import telegram_service_billing_v3_fix as SVC3;SVC3.install(app,B)
    except Exception:log.exception("service billing v3 unavailable")
    try:
        import telegram_sim_service_v2 as SIM;SIM.install(app,B)
    except Exception:log.exception("SIM service legacy layer unavailable")
    try:
        import telegram_topup_invoice as TI
        TI.install(B)
        if getattr(B,"_topup_invoice_install_app",None):B._topup_invoice_install_app(app)
    except Exception:log.exception("topup invoice unavailable")
    import telegram_admin_plus as A
    app.add_handler(CallbackQueryHandler(lambda u,c:_safe_call(A._callback,u,c,B),pattern=r'^adm:'),group=-20)
    try:
        import telegram_announcement_media as AMEDIA;AMEDIA.install(app,B)
    except Exception:log.exception("announcement media unavailable")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_safe_call(A._text,u,c,B)),group=-19)
    try:
        import telegram_admin_entry as AE;AE.install(app,B)
    except Exception:log.exception("admin entry unavailable")
    try:
        import telegram_government_flow_v2 as GV;GV.install(app,B)
    except Exception:log.exception("unified government flow unavailable")
    try:
        import telegram_government_flow_runtime_fix as GF;GF.install(app,B)
    except Exception:log.exception("government flow runtime fix unavailable")
    import partner_pricing as P;P.install_telegram(app,B)
    import telegram_service_pricing as SP;SP.install(app,B)
    import telegram_night_shift_v2 as N;N.install(app,B)
    import telegram_admin_menu_v2 as AM;AM.install(B)
    import telegram_request_control_v2 as RC;RC.install(app,B)
    try:
        import telegram_legacy_callback_bridge as LCB;LCB.install(app,B)
    except Exception:log.exception("legacy callback bridge unavailable")
    try:
        import telegram_partner_code_reliable as PCR;PCR.install(app,B)
    except Exception:log.exception("partner code handler unavailable")
    try:
        import telegram_request_resend_fa as RFA;RFA.install(app,B)
    except Exception:log.exception("request resend handler unavailable")
    import telegram_access_hardening as AH;AH.install(app,B)
    try:
        import telegram_partner_visibility_fix as PV;PV.install(app,B)
    except Exception:log.exception("partner visibility fix unavailable")
    try:
        import telegram_partner_application_gate as PAG;PAG.install(app,B)
    except Exception:log.exception("partner application gate unavailable")
    # IMPORTANT: this must be the final partner-router installation. Several legacy
    # feature layers above mutate B.partner/B.partner_kb; installing the guard only
    # from runtime_patches happens too early and can therefore be overwritten.
    try:
        import telegram_partner_router_guard as PRG;PRG.install()
        log.info("Telegram partner router guard installed LAST")
    except Exception:log.exception("partner router guard final install unavailable")
    B.start=_start;B.langcb=_lang_select;B.statuscb=_status_select
    app.add_handler(TypeHandler(Update,_absolute_startup_callback),group=-1000000)
    log.info("Telegram feature layers installed; absolute startup router installed")

def _self_check():
    required=("main","partner","fida","gov","prt","ptrack","phistory","media","router","admin","cancel")
    missing=[name for name in required if not callable(getattr(B,name,None))]
    if missing:log.error("Telegram runtime self-check FAILED; missing hooks: %s",missing)
    else:log.info("Telegram runtime self-check: core hooks OK")
    if not getattr(B,"_gov_v2",False):log.error("Telegram runtime self-check FAILED; unified government flow is not active")
    else:log.info("Telegram runtime self-check: government v2 active")
    if not getattr(B,"_inline_ui_v2",False):log.error("Telegram runtime self-check FAILED; inline UI v2 is not active")
    else:log.info("Telegram runtime self-check: inline UI v2 active")
    if not getattr(B,"_telegram_language_lock",False):log.error("Telegram runtime self-check FAILED; language lock is not active")
    else:log.info("Telegram runtime self-check: language lock active")

def build():
    token=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip() or os.getenv("TELEGRAM_TOKEN","").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build();app.add_error_handler(_error_handler);app.add_handler(TypeHandler(Update,_diagnostic),group=-1000001);_install_features(app);_self_check()
    app.add_handler(CommandHandler(["start","srart"],_start),group=0)
    app.add_handler(CommandHandler("addpartner",lambda u,c:_safe_call(B.addpartner,u,c)),group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),lambda u,c:_safe_call(B.admin_command,u,c)),group=0)
    app.add_handler(CallbackQueryHandler(lambda u,c:_safe_call(B.admin_cb,u,c),pattern=r'^(tu|pay|req|admin):'),group=0)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,lambda u,c:_safe_call(B.media,u,c)),group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_safe_call(B.router,u,c)),group=1)
    log.info("Canonical Telegram handlers installed");return app
