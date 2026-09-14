"""Canonical Telegram runtime with deterministic feature installation and final routing guards."""
import logging, inspect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters, ApplicationHandlerStop
import bot as B
log=logging.getLogger("netyar.telegram_runtime")
_LANGS={"fa","en","ar"}
_STATUSES={"foreign","iranian"}
WELCOME="سلام و خوش آمدید 🌷\n\nلطفاً زبان موردنظر را انتخاب کنید / Choose your language / اختر اللغة:"
async def _safe_call(fn, update, context):
    try:
        result=fn(update,context)
        if inspect.isawaitable(result): return await result
        return result
    except ApplicationHandlerStop: raise
    except Exception: log.exception("Telegram handler failed: %r",fn); return None
async def _start(update, context):
    user=update.effective_user
    if not update.message or not user:return
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=B.S.get(uid,{})
    B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","lang","status","phone") if k in old}
    await update.message.reply_text(WELCOME,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))
async def _absolute_startup_callback(update,context):
    q=getattr(update,"callback_query",None)
    if not q:return
    data=str(q.data or "").strip()
    if data in {"lang:fa","lang:en","lang:ar","language:fa","language:en","language:ar"}:
        lang=data.split(":",1)[1];await q.answer();uid=q.from_user.id;old=B.S.get(uid,{})
        B.S[uid]={k:old[k] for k in ("partner_id","partner_active","admin","phone") if k in old};B.S[uid]["lang"]=lang
        labels={"fa":("🪪 اتباع هستم","🇮🇷 ایرانی هستم"),"en":("🪪 Foreign national","🇮🇷 Iranian"),"ar":("🪪 أجنبي","🇮🇷 إيراني")}[lang]
        text={"fa":"آیا اتباع هستید یا ایرانی؟","en":"Are you a foreign national or Iranian?","ar":"هل أنت أجنبي أم إيراني؟"}[lang]
        await q.message.reply_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(labels[0],callback_data="startup:foreign"),InlineKeyboardButton(labels[1],callback_data="startup:iranian")]]));raise ApplicationHandlerStop
    if data in {"foreign","iranian","st:foreign","st:iranian","startup:foreign","startup:iranian","status:foreign","status:iranian"}:
        status=data.split(":",1)[1] if ":" in data else data;await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{})
        st["status"]=status;st["citizenship"]=status;st.pop("mode",None);lang=st.get("lang","fa");lang=lang if lang in _LANGS else "fa"
        text={"fa":"منوی خدمات کمک یار مهاجر 👇","en":"Mohajer Helper services 👇","ar":"قائمة خدمات المهاجرين 👇"}[lang] if status=="foreign" else {"fa":"🇮🇷 منوی خدمات ایرانی 👇","en":"🇮🇷 Iranian user menu 👇","ar":"🇮🇷 قائمة المستخدم الإيراني 👇"}[lang]
        await q.message.reply_text(text,reply_markup=B.main(uid));raise ApplicationHandlerStop
def _install_features(app):
    B.start=_start
    try:
        import telegram_startup_button_firewall as SBF;SBF.install(app,B)
    except Exception:log.exception("startup button firewall unavailable")
    try:
        import telegram_business_features as F;F.install(app,B)
    except Exception:log.exception("business features unavailable")
    try:
        import telegram_ui_policy_v2 as UI;UI.install(app,B)
    except Exception:log.exception("ui policy unavailable")
    try:
        import telegram_language_consistency as TLC;TLC.install(B)
    except Exception:log.exception("language consistency unavailable")
    try:
        import telegram_partner_ui_fix as PUI;PUI.install(app,B)
    except Exception:log.exception("partner UI unavailable")
    try:
        import telegram_public_tracking as PT;PT.install(app,B)
    except Exception:log.exception("tracking unavailable")
    try:
        import telegram_service_billing_v3_fix as SVC3;SVC3.install(app,B)
    except Exception:log.exception("billing unavailable")
    try:
        import telegram_sim_service_v2 as SIM;SIM.install(app,B)
    except Exception:log.exception("sim service unavailable")
    try:
        import telegram_topup_invoice as TI
        TI.install(B)
        if getattr(B,"_topup_invoice_install_app",None):B._topup_invoice_install_app(app)
    except Exception:log.exception("topup invoice unavailable")
    try:
        import telegram_admin_plus as A
        app.add_handler(CallbackQueryHandler(lambda u,c:_safe_call(A._callback,u,c,B),pattern=r'^adm:'),group=-20)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_safe_call(A._text,u,c,B)),group=-19)
        B.amenu=A._admin_menu
    except Exception:log.exception("admin plus unavailable")
    for name,fn in (("telegram_announcement_media", "install"),("telegram_admin_entry","install"),("telegram_government_flow_v2","install"),("telegram_government_flow_runtime_fix","install"),("partner_pricing","install_telegram"),("telegram_service_pricing","install"),("telegram_night_shift_v2","install"),("telegram_admin_menu_v2","install"),("telegram_request_control_v2","install"),("telegram_legacy_callback_bridge","install"),("telegram_partner_code_reliable","install"),("telegram_request_resend_fa","install"),("telegram_access_hardening","install"),("telegram_partner_visibility_fix","install"),("telegram_partner_application_gate","install")):
        try:
            m=__import__(name);f=getattr(m,fn,None)
            if callable(f):
                try:f(app,B)
                except TypeError:f(B)
        except Exception:log.exception("optional Telegram layer unavailable: %s",name)
    B.start=_start;app.add_handler(TypeHandler(Update,_absolute_startup_callback),group=-1000000)
    log.info("Telegram canonical feature layers installed")
def _self_check():
    required=("main","partner","fida","gov","prt","ptrack","phistory","media","router","admin","cancel")
    missing=[name for name in required if not callable(getattr(B,name,None))]
    if missing:log.error("Telegram runtime self-check FAILED; missing hooks: %s",missing)
def build():
    token=str(getattr(B,"BOT_TOKEN","") or "").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build()
    _self_check()
    app.add_handler(CommandHandler("start",_start),group=-9000)
    app.add_handler(CommandHandler("addpartner",B.addpartner),group=-100)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),B.admin_command),group=-100)
    app.add_handler(CallbackQueryHandler(B.admin_cb,pattern=r"^(tu|pay|req|admin):"),group=0)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,B.media),group=10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,B.router),group=20)
    _install_features(app)
    B.start=_start
    log.info("Telegram canonical Application built successfully")
    return app
