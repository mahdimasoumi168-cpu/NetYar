"""Canonical Telegram runtime: Persian-only startup and deterministic feature installation."""
import asyncio
import inspect
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ApplicationHandlerStop
import bot as B

log = logging.getLogger("netyar.telegram_runtime")
WELCOME = ("👋 سلام!\n\n" "به سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\n" "اینجا تلاش کرده‌ایم خدمات موردنیاز شما را به‌صورت سریع، ساده و آنلاین در اختیارتان قرار دهیم تا بدون سردرگمی بتوانید خدمت موردنظر خود را دریافت یا پیگیری کنید.\n\n" "🚀 بات، کمک یار مهاجر؛ خدماتی برای شما، درآمدی برای همه\n\n" "📌 برای شروع دریافت خدمات، روی دکمه «🛎 استفاده از خدمات» بزنید.")
RESTART = "🔄 شروع مجدد"
USE_SERVICES = "🛎 استفاده از خدمات"


def _restart_keyboard():
    return ReplyKeyboardMarkup([[RESTART]], resize_keyboard=True, is_persistent=True)


def _services_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(USE_SERVICES, callback_data="start:services")]])


def _offhours_state():
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
    return _offhours_state()[0]


async def _reply_closed(message):
    closed, text, markup = _offhours_state()
    if closed:
        await message.reply_text(text, reply_markup=markup)
        return True
    return False


async def _safe_call(fn, update, context, *extra):
    try:
        result = fn(update, context, *extra)
        return await result if inspect.isawaitable(result) else result
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("Telegram handler failed: %r", fn)
        return None


async def _start(update, context):
    user = update.effective_user
    if not user:
        return
    if await _reply_closed(update.effective_message):
        raise ApplicationHandlerStop
    uid = user.id
    try:
        B.db.user("telegram", uid, user.username, user.full_name)
    except Exception:
        log.exception("user persistence")
    old = dict(B.S.get(uid, {}) or {})
    # Preserve privileged/session flags when /start is used. Previously the
    # canonical start handler rebuilt S[uid] with only the language, which could
    # make an administrator lose the management button after pressing Start.
    was_admin = bool(old.get("admin") is True)
    try:
        was_admin = was_admin or bool(B.admin(uid))
    except Exception:
        pass
    B.S[uid] = {"lang": "fa"}
    if was_admin:
        B.S[uid]["admin"] = True
    if not old.get("partner_logged_out"):
        for k in ("partner_id", "partner_active"):
            if k in old:
                B.S[uid][k] = old[k]
    else:
        B.S[uid]["partner_logged_out"] = True
    if update.message:
        await update.message.reply_text(WELCOME, reply_markup=_services_keyboard())
        await update.message.reply_text(RESTART, reply_markup=_restart_keyboard())
    raise ApplicationHandlerStop


async def _restart(update, context):
    if update.effective_message and await _reply_closed(update.effective_message):
        raise ApplicationHandlerStop
    return await _start(update, context)


async def _services_callback(update, context):
    q = getattr(update, "callback_query", None)
    if not q or q.data != "start:services":
        return
    if _is_offhours():
        try:
            await q.answer("❌ خارج از ساعت کاری است.", show_alert=True)
        except Exception:
            pass
        if q.message:
            await _reply_closed(q.message)
        raise ApplicationHandlerStop
    await q.answer()
    uid = q.from_user.id
    B.S.setdefault(uid, {})["lang"] = "fa"
    await q.message.reply_text(
        "نوع کاربری خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"),
            InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian"),
        ]]),
    )
    raise ApplicationHandlerStop


async def _blocked_language_callback(update, context):
    q = getattr(update, "callback_query", None)
    if not q:
        return
    data = str(q.data or "").strip()
    if not (data.startswith("lang:") or data.startswith("language:")):
        return
    if _is_offhours():
        try:
            await q.answer("❌ خارج از ساعت کاری است.", show_alert=True)
        except Exception:
            pass
        if q.message:
            await _reply_closed(q.message)
        raise ApplicationHandlerStop
    B.S.setdefault(q.from_user.id, {})["lang"] = "fa"
    await q.answer("زبان فارسی است.")
    await q.message.reply_text("لطفاً از دکمه «🛎 استفاده از خدمات» استفاده کنید.", reply_markup=_services_keyboard())
    raise ApplicationHandlerStop


def _install_features(app):
    for module, fn, args in (
        ("telegram_offhours_partner_gate_v2", "install", (app, B)),
        ("telegram_offhours_absolute_start_guard", "install", (app, B)),
        ("telegram_startup_button_firewall", "install", (app, B)),
        ("telegram_business_features", "install", (app, B)),
        ("telegram_ui_policy_v2", "install", (app, B)),
        ("telegram_partner_ui_fix", "install", (app, B)),
        ("telegram_public_tracking", "install", (app, B)),
        ("telegram_service_billing_v3_fix", "install", (app, B)),
        ("telegram_sim_service_v2", "install", (app, B)),
        ("telegram_irancell_partner_service", "install", (app, B)),
    ):
        try:
            m = __import__(module)
            f = getattr(m, fn, None)
            if callable(f):
                result = f(*args)
                if inspect.isawaitable(result):
                    asyncio.run(result)
        except Exception:
            log.exception("Telegram layer unavailable: %s", module)
    try:
        import telegram_language_consistency as TLC
        result = TLC.install(B)
        if inspect.isawaitable(result):
            asyncio.run(result)
    except Exception:
        log.exception("language consistency unavailable")
    try:
        import telegram_topup_invoice as TI
        result = TI.install(B)
        if inspect.isawaitable(result):
            asyncio.run(result)
        if getattr(B, "_topup_invoice_install_app", None):
            B._topup_invoice_install_app(app)
    except Exception:
        log.exception("topup invoice unavailable")
    try:
        import telegram_admin_plus as A
        async def admin_plus_callback(update, context):
            return await _safe_call(A._callback, update, context, B)
        async def admin_plus_text(update, context):
            return await _safe_call(A._text, update, context, B)
        app.add_handler(CallbackQueryHandler(admin_plus_callback, pattern=r'^adm:'), group=-20)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plus_text), group=-19)
        B.amenu = A._admin_menu
    except Exception:
        log.exception("admin plus unavailable")
    for name, fn in (("telegram_announcement_media", "install"), ("telegram_admin_entry", "install"), ("telegram_government_flow_v2", "install"), ("telegram_government_flow_runtime_fix", "install"), ("telegram_government_balance_guard", "install"), ("partner_pricing", "install_telegram"), ("telegram_service_pricing", "install"), ("telegram_admin_menu_v2", "install"), ("telegram_request_control_v2", "install"), ("telegram_legacy_callback_bridge", "install"), ("telegram_partner_code_reliable", "install"), ("telegram_request_resend_fa", "install"), ("telegram_access_hardening", "install"), ("telegram_partner_visibility_fix", "install"), ("telegram_partner_application_gate", "install")):
        try:
            m = __import__(name)
            f = getattr(m, fn, None)
            if callable(f):
                result = f(app, B)
                if inspect.isawaitable(result):
                    asyncio.run(result)
        except TypeError:
            try:
                result = f(B)
                if inspect.isawaitable(result):
                    asyncio.run(result)
            except Exception:
                log.exception("optional Telegram layer unavailable: %s", name)
        except Exception:
            log.exception("optional Telegram layer unavailable: %s", name)
    for module, label in (("telegram_partner_runtime_fix_v31", "partner runtime fix v31"), ("telegram_partner_final_router_v29", "partner router v29"), ("telegram_absolute_callback_hardening_v30", "absolute callback hardening v30"), ("telegram_management_only_v32", "management-only partner UI v32"), ("telegram_session_and_context_hardening_v33", "session/context hardening v33"), ("telegram_final_admin_navigation_v3", "final admin navigation v3"), ("telegram_partner_navigation_final_v33", "partner navigation v33"), ("telegram_final_iranian_menu_v38", "Iranian menu v38"), ("telegram_final_request_partner_guard_v1", "final request/partner routing guard v1")):
        try:
            m = __import__(module)
            result = m.install(app, B)
            if inspect.isawaitable(result):
                asyncio.run(result)
            log.info("REAL runtime: %s installed", label)
        except Exception:
            log.exception("%s unavailable", label)
    if getattr(B, "_partner_final_router_v29", False) and getattr(B, "_absolute_callback_v30", False):
        log.info("REAL runtime final layers OK: v29 + v30 + v33")
    else:
        log.error("REAL runtime final layers FAILED: v29=%s v30=%s v33=%s", getattr(B, "_partner_final_router_v29", False), getattr(B, "_absolute_callback_v30", False), getattr(B, "_session_context_hardening_v33", False))
    B.start = _start
    app.add_handler(CommandHandler("start", _start), group=-10000000)
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"), _restart), group=-9999999)
    app.add_handler(CallbackQueryHandler(_blocked_language_callback, pattern=r"^(lang|language):"), group=-9999998)
    app.add_handler(CallbackQueryHandler(_services_callback, pattern=r"^start:services$"), group=-9999997)
    log.info("Telegram Persian-only authoritative startup handlers installed")


def _self_check():
    required = ("main", "partner", "fida", "gov", "prt", "ptrack", "phistory", "media", "router", "admin", "cancel")
    missing = [name for name in required if not callable(getattr(B, name, None))]
    if missing:
        log.error("Telegram runtime self-check FAILED; missing hooks: %s", missing)


def build():
    token = str(getattr(B, "BOT_TOKEN", "") or "").strip()
    if not token:
        raise RuntimeError("Telegram bot token is missing")
    app = Application.builder().token(token).build()
    _self_check()
    app.add_handler(CommandHandler("addpartner", B.addpartner), group=-100)
    app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"), B.admin_command), group=-100)
    app.add_handler(CallbackQueryHandler(B.admin_cb, pattern=r"^(tu|pay|req|admin):"), group=0)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, B.media), group=10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, B.router), group=20)
    _install_features(app)
    B.start = _start
    log.info("Canonical Telegram Application built successfully; Persian-only startup active")
    return app
