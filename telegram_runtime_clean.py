"""Canonical Telegram runtime with one Application and deterministic feature installation."""
import logging, os, inspect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters
import bot as B
log=logging.getLogger("netyar.telegram_runtime")
_CALLBACK_SEEN=set()

async def _safe_call(fn, update, context):
    try:
        result=fn(update,context)
        if inspect.isawaitable(result): return await result
        return result
    except Exception:
        log.exception("Telegram handler failed: %r",fn)
        return None

def _diagnostic(update, context):
    try:
        if update.message is not None: log.info("Telegram update id=%s user=%s text=%r",update.update_id,getattr(update.effective_user,"id",None),update.message.text)
        elif update.callback_query is not None: log.info("Telegram callback id=%s user=%s data=%r",update.update_id,getattr(update.effective_user,"id",None),update.callback_query.data)
    except Exception: log.exception("Telegram diagnostic failed")

async def _start(update, context):
    user=update.effective_user
    if not update.message or not user:return
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","lang","status","phone") if k in old}
    await update.message.reply_text("سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))

def _claim(q):
    cid=getattr(q,"id",None)
    if not cid:return True
    if cid in _CALLBACK_SEEN:return False
    _CALLBACK_SEEN.add(cid)
    if len(_CALLBACK_SEEN)>2000:_CALLBACK_SEEN.clear();_CALLBACK_SEEN.add(cid)
    return True

async def _lang_select(update,context):
    q=update.callback_query
    if not q:return
    if not _claim(q):
        try:await q.answer()
        except Exception:pass
        return
    await q.answer();uid=q.from_user.id;lang=str(q.data or "").split(":",1)[-1]
    if lang not in {"fa","en","ar"}:lang="fa"
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","phone") if k in old};B.S[uid]["lang"]=lang
    texts={"fa":"آیا اتباع هستید یا ایرانی؟","en":"Are you a foreign national or Iranian?","ar":"هل أنت أجنبي أم إيراني؟"}
    labels={"fa":("🪪 اتباع هستم","🇮🇷 ایرانی هستم"),"en":("🪪 Foreign national","🇮🇷 Iranian"),"ar":("🪪 أجنبي","🇮🇷 إيراني")}[lang]
    return await q.message.reply_text(texts[lang],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(labels[0],callback_data="st:foreign"),InlineKeyboardButton(labels[1],callback_data="st:iranian")]]))

async def _status_select(update,context):
    q=update.callback_query
    if not q:return
    if not _claim(q):
        try:await q.answer()
        except Exception:pass
        return
    await q.answer();uid=q.from_user.id;status=str(q.data or "").split(":",1)[-1];st=B.S.setdefault(uid,{})
    if status not in {"foreign","iranian"}: return
    st["status"]=status;st.pop("mode",None);lang=st.get("lang","fa")
    text={"fa":"منوی خدمات کمک یار مهاجر 👇","en":"Mohajer Helper services 👇","ar":"قائمة خدمات المهاجرين 👇"}[lang] if status=="foreign" else {"fa":"🇮🇷 منوی خدمات ایرانی 👇","en":"🇮🇷 Iranian user menu 👇","ar":"🇮🇷 قائمة المستخدم الإيراني 👇"}[lang]
    return await q.message.reply_text(text,reply_markup=B.main(uid))

def _install_features(app):
    B.start=_start
    import telegram_business_features as F;F.install(app,B)
    import telegram_ui_policy_v2 as UI;UI.install(app,B)
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
        import telegram_partner_application_gate as PAG;PAG.install(app,B)
    except Exception:log.exception("partner application gate unavailable")
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
    B.start=_start;B.langcb=_lang_select;B.statuscb=_status_select
    log.info("Telegram feature layers installed")

def build():
    token=os.getenv("BOT_TOKEN","").strip() or os.getenv("TELEGRAM_BOT_TOKEN","").strip() or os.getenv("TELEGRAM_TOKEN","").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build();app.add_handler(TypeHandler(Update,_diagnostic),group=-1000);_install_features(app)
    app.add_handler(CommandHandler(["start","srart"],_start),group=0)
    app.add_handler(CommandHandler("addpartner",lambda u,c:_safe_call(B.addpartner,u,c)),group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),lambda u,c:_safe_call(B.admin_command,u,c)),group=0)
    # Route through the final function stored on B so feature layers cannot leave
    # the stale status handler behind. There is exactly one lang/status dispatcher.
    app.add_handler(CallbackQueryHandler(lambda u,c:_safe_call(B.langcb,u,c),pattern=r'^lang:'),group=0)
    app.add_handler(CallbackQueryHandler(lambda u,c:_safe_call(B.statuscb,u,c),pattern=r'^st:'),group=0)
    app.add_handler(CallbackQueryHandler(lambda u,c:_safe_call(B.admin_cb,u,c),pattern=r'^(tu|pay|req|admin):'),group=0)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,lambda u,c:_safe_call(B.media,u,c)),group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_safe_call(B.router,u,c)),group=1)
    log.info("Canonical Telegram handlers installed");return app