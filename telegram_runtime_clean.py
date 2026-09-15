"""Canonical Telegram runtime: Persian-only startup and deterministic feature installation."""
import logging, inspect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters, ApplicationHandlerStop
import bot as B
log=logging.getLogger("netyar.telegram_runtime")
WELCOME=("👋 سلام!\n\n" "به سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\n" "اینجا تلاش کرده‌ایم خدمات موردنیاز شما را به‌صورت سریع، ساده و آنلاین در اختیارتان قرار دهیم تا بدون سردرگمی بتوانید خدمت موردنظر خود را دریافت یا پیگیری کنید.\n\n" "🚀 بات، کمک یار مهاجر؛ خدماتی برای شما، درآمدی برای همه\n\n" "📌 برای شروع دریافت خدمات، روی دکمه «🛎 استفاده از خدمات» بزنید.")
RESTART="🔄 شروع مجدد"
USE_SERVICES="🛎 استفاده از خدمات"

def _restart_keyboard(): return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,is_persistent=True)
def _services_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton(USE_SERVICES,callback_data="start:services")]])

def _offhours_state():
    """Return canonical closed-hours helpers; fail closed if unavailable."""
    try:
        from telegram_offhours_partner_gate_v2 import _is_open, _closed_text, _closed_markup
        return (not bool(_is_open(B))), _closed_text(B), _closed_markup()
    except Exception:
        log.exception("canonical off-hours gate unavailable")
        return True, "❌ ربات در حال حاضر خارج از ساعت کاری است.\n\n🚫 خدمات عمومی در این زمان مجاز نیست.", InlineKeyboardMarkup([
            [InlineKeyboardButton(RESTART, callback_data="off:restart")],
            [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
        ])

def _is_offhours():
    closed, _, _ = _offhours_state()
    return closed

async def _reply_closed(message):
    closed, text, markup = _offhours_state()
    if closed:
        await message.reply_text(text, reply_markup=markup)
        return True
    return False

async def _safe_call(fn, update, context, *extra):
    try:
        result=fn(update,context,*extra)
        if inspect.isawaitable(result): return await result
        return result
    except ApplicationHandlerStop: raise
    except Exception:
        log.exception("Telegram handler failed: %r",fn)
        return None

async def _start(update, context):
    user=update.effective_user
    if not user:return
    # IMPORTANT: this check must happen before the normal welcome/menu flow.
    # The runtime /start handler is installed at a higher priority than the
    # generic off-hours callback/message gates, so it must hard-stop itself.
    if await _reply_closed(update.effective_message):
        raise ApplicationHandlerStop
    uid=user.id
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=dict(B.S.get(uid,{}) or {})
    B.S[uid]={"lang":"fa"}
    if not old.get("partner_logged_out"):
        for k in ("partner_id","partner_active"):
            if k in old:B.S[uid][k]=old[k]
    else:
        B.S[uid]["partner_logged_out"]=True
    if update.message:
        await update.message.reply_text(WELCOME,reply_markup=_services_keyboard())
        await update.message.reply_text(RESTART,reply_markup=_restart_keyboard())
    raise ApplicationHandlerStop

async def _restart(update, context):
    # Keep restart completely blocked outside working hours.
    if update.effective_message and await _reply_closed(update.effective_message):
        raise ApplicationHandlerStop
    return await _start(update,context)

async def _services_callback(update,context):
    q=getattr(update,"callback_query",None)
    if not q or q.data!="start:services":return
    if _is_offhours():
        try: await q.answer("❌ خارج از ساعت کاری است.",show_alert=True)
        except Exception: pass
        if q.message: await _reply_closed(q.message)
        raise ApplicationHandlerStop
    await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
    st["lang"]="fa"; st.pop("mode",None)
    await q.message.reply_text("نوع کاربری خود را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم",callback_data="st:foreign"),InlineKeyboardButton("🇮🇷 ایرانی هستم",callback_data="st:iranian")]]))
    raise ApplicationHandlerStop

async def _blocked_language_callback(update,context):
    q=getattr(update,"callback_query",None)
    if not q:return
    data=str(q.data or "").strip()
    if not (data.startswith("lang:") or data.startswith("language:")):return
    if _is_offhours():
        try: await q.answer("❌ خارج از ساعت کاری است.",show_alert=True)
        except Exception: pass
        if q.message: await _reply_closed(q.message)
        raise ApplicationHandlerStop
    uid=q.from_user.id; B.S.setdefault(uid,{})["lang"]="fa"
    await q.answer("زبان فارسی است.")
    await q.message.reply_text("لطفاً از دکمه «🛎 استفاده از خدمات» استفاده کنید.",reply_markup=_services_keyboard())
    raise ApplicationHandlerStop

def _install_features(app):
    B.start=_start
    # Install the canonical off-hours stack explicitly in the actual runtime.
    # These guards must exist in the live Application, not only in entrypoint.
    try:
        import telegram_offhours_partner_gate_v2 as OH
        OH.install(app,B)
    except Exception:log.exception("off-hours partner gate unavailable")
    try:
        import telegram_offhours_absolute_start_guard as OAS
        OAS.install(app,B)
    except Exception:log.exception("absolute off-hours start guard unavailable")
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
        import telegram_irancell_partner_service as IRSIM;IRSIM.install(app,B)
    except Exception:log.exception("Irancell partner service unavailable")
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
    for name,fn in (("telegram_announcement_media","install"),("telegram_admin_entry","install"),("telegram_government_flow_v2","install"),("telegram_government_flow_runtime_fix","install"),("telegram_government_balance_guard","install"),("partner_pricing","install_telegram"),("telegram_service_pricing","install"),("telegram_admin_menu_v2","install"),("telegram_request_control_v2","install"),("telegram_legacy_callback_bridge","install"),("telegram_partner_code_reliable","install"),("telegram_request_resend_fa","install"),("telegram_access_hardening","install"),("telegram_partner_visibility_fix","install"),("telegram_partner_application_gate","install")):
        try:
            m=__import__(name);f=getattr(m,fn,None)
            if callable(f):
                try:f(app,B)
                except TypeError:f(B)
        except Exception:log.exception("optional Telegram layer unavailable: %s",name)
    B.start=_start
    app.add_handler(CommandHandler("start",_start),group=-10000000)
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"),_restart),group=-9999999)
    app.add_handler(CallbackQueryHandler(_blocked_language_callback,pattern=r"^(lang|language):"),group=-9999998)
    app.add_handler(CallbackQueryHandler(_services_callback,pattern=r"^start:services$"),group=-9999997)
    log.info("Telegram Persian-only authoritative startup handlers installed")

def _self_check():
    required=("main","partner","fida","gov","prt","ptrack","phistory","media","router","admin","cancel")
    missing=[name for name in required if not callable(getattr(B,name,None))]
    if missing:log.error("Telegram runtime self-check FAILED; missing hooks: %s",missing)

def build():
    token=str(getattr(B,"BOT_TOKEN","") or "").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build(); _self_check()
    app.add_handler(CommandHandler("addpartner",B.addpartner),group=-100)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),B.admin_command),group=-100)
    app.add_handler(CallbackQueryHandler(B.admin_cb,pattern=r"^(tu|pay|req|admin):"),group=0)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,B.media),group=10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,B.router),group=20)
    _install_features(app); B.start=_start
    log.info("Canonical Telegram Application built successfully; Persian-only startup active")
    return app
