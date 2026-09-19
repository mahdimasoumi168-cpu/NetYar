"""Canonical Telegram runtime: Persian-only startup and deterministic feature installation."""
import asyncio, inspect, logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ApplicationHandlerStop
import bot as B
log=logging.getLogger("netyar.telegram_runtime")
WELCOME=("👋 سلام!\n\nبه سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\n"
"اینجا تلاش کرده‌ایم خدمات موردنیاز شما را به‌صورت سریع، ساده و آنلاین در اختیارتان قرار دهیم تا بدون سردرگمی بتوانید خدمت موردنظر خود را دریافت یا پیگیری کنید.\n\n"
"🚀 بات، کمک یار مهاجر؛ خدماتی برای شما، درآمدی برای همه\n\n📌 برای شروع دریافت خدمات، روی دکمه «🛎 استفاده از خدمات» بزنید.")
RESTART="🔄 شروع مجدد"; USE_SERVICES="🛎 استفاده از خدمات"
def _restart_keyboard(): return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,is_persistent=True)
def _services_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton(USE_SERVICES,callback_data="start:services")]])
def _offhours_state(uid=None):
    try:
        from telegram_offhours_partner_gate_v2 import _clock_is_open, night_access_open, _closed_markup, _closed_text
        if _clock_is_open(B): return False, "", None
        if uid is not None and night_access_open(B, uid): return False, "", None
        return True, _closed_text(B), _closed_markup()
    except Exception:
        log.exception("offhours state unavailable")
        return False, "", None
def _is_offhours(uid=None):
    return bool(_offhours_state(uid)[0])

def _full_bot_open(uid=None):
    try:
        if uid is not None and B.admin(uid):
            return True
    except Exception:
        pass
    try:
        return str(B.db.setting("bot_enabled", "1") or "1") == "1"
    except Exception:
        return True

async def _reply_full_closed(message):
    await message.reply_text("🔒 ربات در حال حاضر به‌طور کامل بسته است.\\n\\n🚫 هیچ خدمت، ثبت درخواست یا ادامه فرایندی در این زمان امکان‌پذیر نیست.")
    return True
def _night_worker_active(uid):
    try:
        from telegram_offhours_partner_gate_v2 import _clock_is_open, is_night_worker
        return (not _clock_is_open(B)) and bool(is_night_worker(B,uid))
    except Exception:
        return False

async def _reply_closed(message,uid=None):
    try:
        from telegram_offhours_partner_gate_v2 import _clock_is_open, night_access_open, _closed_markup, _closed_text
        if _clock_is_open(B): return False
        if uid is not None and night_access_open(B,uid): return False
        await message.reply_text(_closed_text(B),reply_markup=_closed_markup())
        return True
    except Exception:
        return False
async def _safe_call(fn,update,context,*extra):
    try:
        r=fn(update,context,*extra); return await r if inspect.isawaitable(r) else r
    except ApplicationHandlerStop: raise
    except Exception: log.exception("Telegram handler failed: %r",fn); return None
async def _start(update,context):
    user=update.effective_user
    if not user:return
    uid=user.id
    if not _full_bot_open(uid):
        await _reply_full_closed(update.effective_message)
        raise ApplicationHandlerStop
    if await _reply_closed(update.effective_message,uid):
        raise ApplicationHandlerStop
    if _night_worker_active(uid):
        try:
            from telegram_offhours_partner_gate_v2 import _night_partner_markup
            await update.effective_message.reply_text(
                "🌙 پنل همکاران شیفت شب فعال است.",
                reply_markup=_night_partner_markup(B,uid),
            )
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("night partner menu unavailable")
    
    try:B.db.user("telegram",uid,user.username,user.full_name)
    except Exception:log.exception("user persistence")
    old=dict(B.S.get(uid,{}) or {}); was_admin=bool(old.get("admin") is True)
    try:was_admin=was_admin or bool(B.admin(uid))
    except Exception:pass
    B.S[uid]={"lang":"fa"}
    if was_admin:B.S[uid]["admin"]=True
    if not old.get("partner_logged_out"):
        for k in ("partner_id","partner_active"):
            if k in old:B.S[uid][k]=old[k]
    else:B.S[uid]["partner_logged_out"]=True
    if update.message:
        await update.message.reply_text(WELCOME,reply_markup=_services_keyboard()); await update.message.reply_text(RESTART,reply_markup=_restart_keyboard())
    raise ApplicationHandlerStop
async def _restart(update,context):
    uid=getattr(getattr(update,"effective_user",None),"id",None)
    if uid is not None and not _full_bot_open(uid):
        await _reply_full_closed(update.effective_message)
        raise ApplicationHandlerStop
    if update.effective_message and await _reply_closed(update.effective_message,uid):raise ApplicationHandlerStop
    return await _start(update,context)
async def _services_callback(update,context):
    q=getattr(update,"callback_query",None)
    if not q or q.data!="start:services":return
    if not _full_bot_open(q.from_user.id):
        try:await q.answer("🔒 ربات کاملاً بسته است.",show_alert=True)
        except Exception:pass
        await _reply_full_closed(q.message)
        raise ApplicationHandlerStop
    if await _reply_closed(q.message, q.from_user.id):
        raise ApplicationHandlerStop
    await q.answer(); uid=q.from_user.id; B.S.setdefault(uid,{})["lang"]="fa"
    await q.message.reply_text("نوع کاربری خود را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم",callback_data="st:foreign"),InlineKeyboardButton("🇮🇷 ایرانی هستم",callback_data="st:iranian")]])); raise ApplicationHandlerStop
async def _blocked_language_callback(update,context):
    q=getattr(update,"callback_query",None)
    if not q:return
    data=str(q.data or "").strip()
    if not(data.startswith("lang:") or data.startswith("language:")):return
    if not _full_bot_open(q.from_user.id):
        try:await q.answer("🔒 ربات کاملاً بسته است.",show_alert=True)
        except Exception:pass
        await _reply_full_closed(q.message)
        raise ApplicationHandlerStop
    B.S.setdefault(q.from_user.id,{})["lang"]="fa"; await q.answer("زبان فارسی است."); await q.message.reply_text("لطفاً از دکمه «🛎 استفاده از خدمات» استفاده کنید.",reply_markup=_services_keyboard()); raise ApplicationHandlerStop

def _install_features(app):
    try:
        import telegram_absolute_access_owner_v1 as AA
        AA.install(app,B)
        log.info("RUNTIME ABSOLUTE ACCESS OWNER LOCKED: telegram_absolute_access_owner_v1")
    except Exception:
        log.exception("CRITICAL: absolute access owner unavailable")
        raise
    first=("telegram_global_full_close_gate","telegram_offhours_partner_gate_v2","telegram_night_shift_consistency","telegram_offhours_absolute_start_guard","telegram_startup_button_firewall","telegram_business_features","telegram_ui_policy_v2","telegram_partner_ui_fix","telegram_public_tracking","telegram_service_billing_v3_fix","telegram_government_strict_validation")
    for module in first:
        try:
            m=__import__(module); f=getattr(m,"install",None)
            if callable(f):
                r=f(app,B)
                if inspect.isawaitable(r):asyncio.run(r)
        except Exception:log.exception("Telegram layer unavailable: %s",module)
    try:
        import telegram_language_consistency as TLC; r=TLC.install(B)
        if inspect.isawaitable(r):asyncio.run(r)
    except Exception:log.exception("language consistency unavailable")
    try:
        import telegram_topup_invoice as TI; r=TI.install(B)
        if inspect.isawaitable(r):asyncio.run(r)
        if getattr(B,"_topup_invoice_install_app",None):B._topup_invoice_install_app(app)
    except Exception:log.exception("topup invoice unavailable")
    try:
        import telegram_admin_plus as A
        async def admin_plus_callback(update,context):return await _safe_call(A._callback,update,context,B)
        async def admin_plus_text(update,context):return await _safe_call(A._text,update,context,B)
        app.add_handler(CallbackQueryHandler(admin_plus_callback,pattern=r'^adm:'),group=-20); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,admin_plus_text),group=-19); B.amenu=A._admin_menu
    except Exception:log.exception("admin plus unavailable")
    legacy=(("telegram_announcement_media","install"),("telegram_admin_entry","install"),("telegram_government_flow_v2","install"),("telegram_government_flow_runtime_fix","install"),("telegram_government_balance_guard","install"),("partner_pricing","install_telegram"),("telegram_service_pricing","install"),("telegram_admin_menu_v2","install"),("telegram_request_control_v2","install"),("telegram_legacy_callback_bridge","install"),("telegram_partner_code_reliable","install"),("telegram_request_resend_fa","install"),("telegram_access_hardening","install"),("telegram_partner_visibility_fix","install"),("telegram_partner_application_gate","install"))
    for name,fn in legacy:
        try:
            m=__import__(name); f=getattr(m,fn,None)
            if callable(f):
                r=f(app,B)
                if inspect.isawaitable(r):asyncio.run(r)
        except TypeError:
            try:
                r=f(B)
                if inspect.isawaitable(r):asyncio.run(r)
            except Exception:log.exception("optional Telegram layer unavailable: %s",name)
        except Exception:log.exception("optional Telegram layer unavailable: %s",name)
    final=(("telegram_partner_runtime_fix_v31","partner runtime fix v31"),("telegram_partner_final_router_v29","partner router v29"),("telegram_absolute_callback_hardening_v30","absolute callback hardening v30"),("telegram_management_only_v32","management-only partner UI v32"),("telegram_session_and_context_hardening_v33","session/context hardening v33"),("telegram_final_admin_navigation_v3","final admin navigation v3"),("telegram_partner_navigation_final_v33","partner navigation v33"),("telegram_final_iranian_menu_v38","Iranian menu v38"),("sizpay_gateway","SizPay gateway"),("telegram_final_request_partner_guard_v1","final request/partner routing guard v1"),("telegram_security_code_image_flow_v4","security-code image workflow v4"))
    for module,label in final:
        try:
            m=__import__(module); r=m.install(app,B)
            if inspect.isawaitable(r):asyncio.run(r)
            log.info("REAL runtime: %s installed",label)
        except Exception:log.exception("%s unavailable",label)
    try:
        import telegram_partner_logout_fix as PLF
        PLF.install(B)
        log.info("RUNTIME PARTNER LOGOUT OWNER LOCKED: telegram_partner_logout_fix")
    except Exception:
        log.exception("CRITICAL: partner logout persistence unavailable")
        raise
    try:
        import telegram_offhours_partner_gate_v2 as G24
        G24.enforce_24x7(B)
        log.info("RUNTIME 24/7 ACCESS OWNER LOCKED: telegram_offhours_partner_gate_v2")
    except Exception:
        log.exception("CRITICAL: 24/7 access enforcement unavailable")
        raise
    try:
        import telegram_canonical_admin_final as CAF; CAF.install(app,B)
        import telegram_admin_ui_firewall_v1 as AF; AF.install(app,B)
        import telegram_canonical_request_flow_v1 as CR; CR.install(app,B)
        try:
            import telegram_final_payment_router_v1 as FPR; FPR.install(app,B)
            log.info("RUNTIME PAYMENT OWNER LOCKED: telegram_final_payment_router_v1")
        except Exception:
            log.exception("CRITICAL: universal payment router unavailable")
            raise
        try:
            import telegram_admin_service_price_sequence as GSP; GSP.install(app,B)
            log.info("RUNTIME GLOBAL SERVICE PRICING OWNER LOCKED: telegram_admin_service_price_sequence")
        except Exception:
            log.exception("CRITICAL: global service pricing unavailable")
        try:
            import telegram_partner_pricing_stable as PPS; PPS.install(app,B)
            log.info("RUNTIME PARTNER PRICING OWNER LOCKED: telegram_partner_pricing_stable")
        except Exception:
            log.exception("CRITICAL: partner pricing owner unavailable")
        try:
            import telegram_admin_partner_chat as APC; APC.install(app,B)
            log.info("RUNTIME PARTNER CHAT OWNER LOCKED: telegram_admin_partner_chat")
        except Exception:
            log.exception("CRITICAL: admin-partner chat unavailable")
        try:
            import telegram_admin_controls_v8 as AC8; AC8.install(app,B)
            log.info("RUNTIME ADMIN CONTROLS OWNER LOCKED: telegram_admin_controls_v8")
        except Exception:
            log.exception("CRITICAL: admin controls v8 unavailable")
            raise
        log.info("RUNTIME ADMIN OWNER LOCKED: telegram_admin_controls_v8")
        try:
            import telegram_partner_registration as PR
            PR.install(app,B)
            log.info("RUNTIME PARTNER MEMBERSHIP OWNER LOCKED: telegram_partner_registration")
        except Exception:
            log.exception("CRITICAL: partner membership onboarding unavailable")
            raise

        log.info("RUNTIME REQUEST OWNER LOCKED: telegram_canonical_request_flow_v1")
        log.info("RUNTIME ADMIN AMENU OWNER: %s.%s",getattr(B.amenu,"__module__","?"),getattr(B.amenu,"__name__","?"))
    except Exception:log.exception("CRITICAL: canonical admin owner/firewall unavailable"); raise
    try:
        import desktop_agent_api_clean as DA
        DA.install(app,B)
        log.info("RUNTIME DESKTOP AGENT API OWNER ACTIVE")
    except Exception:
        log.exception("Desktop Agent API installation failed")
    B.start=_start
    app.add_handler(CommandHandler("start",_start),group=-10000000)
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"),_restart),group=-9999999)
    app.add_handler(CallbackQueryHandler(_blocked_language_callback,pattern=r"^(lang|language):"),group=-9999998)
    app.add_handler(CallbackQueryHandler(_services_callback,pattern=r"^start:services$"),group=-9999997)

def _self_check():
    required=("main","partner","fida","gov","ptrack","phistory","media","router","admin","cancel"); missing=[n for n in required if not callable(getattr(B,n,None))]
    if missing:log.error("Telegram runtime self-check FAILED; missing hooks: %s",missing)
def build():
    token=str(getattr(B,"BOT_TOKEN","") or "").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")
    app=Application.builder().token(token).build(); _self_check()
    app.add_handler(CommandHandler("addpartner",B.addpartner),group=-100); app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),B.admin_command),group=-100); app.add_handler(CallbackQueryHandler(B.admin_cb,pattern=r"^(tu|pay|req|admin):"),group=0); app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,B.media),group=10); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,B.router),group=20)
    _install_features(app); B.start=_start; log.info("Canonical Telegram Application built successfully; Persian-only startup active"); return app
