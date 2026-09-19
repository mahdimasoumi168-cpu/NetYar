"""Absolute Telegram access owner for full-close and partner entry.

This layer is intentionally tiny: it owns only the security boundary. It never
implements service flows, so legacy feature handlers remain available behind it.
"""
import logging
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.absolute_access_owner")
KEY = "bot_enabled"
PARTNER_LABELS = {"👥 پنل همکاران", "🔵 👥 پنل همکاران", "پنل همکاران"}

def _enabled(B):
    try:
        return str(B.db.setting(KEY, "1") or "1") == "1"
    except Exception:
        return True

def _admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        return False

def _closed_text():
    return (
        "🔒 ربات در حال حاضر به‌طور کامل بسته است.\n\n"
        "🚫 هیچ خدمت، ثبت درخواست، ورود به پنل همکاران یا ادامه فرایندی "
        "برای کاربران عادی امکان‌پذیر نیست.\n\n"
        "فقط مدیریت می‌تواند ربات را دوباره باز کند."
    )

def _night_public_open(B):
    try:
        from telegram_offhours_partner_gate_v2 import _clock_is_open, night_public_open
        return (not _clock_is_open(B)) and bool(night_public_open(B))
    except Exception:
        return False

async def _callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q or _enabled(B) or _admin(B, q.from_user.id) or _night_public_open(B):
        return
    try:
        await q.answer("🔒 ربات کاملاً بسته است.", show_alert=True)
    except Exception:
        pass
    try:
        await q.message.reply_text(_closed_text())
    finally:
        raise ApplicationHandlerStop

async def _message(update, context, B):
    u = getattr(update, "effective_user", None)
    msg = getattr(update, "effective_message", None)
    if not u or not msg or _enabled(B) or _admin(B, u.id) or _night_public_open(B):
        return
    await msg.reply_text(_closed_text())
    raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, "_absolute_access_owner_v1", False):
        return True
    app.add_handler(CallbackQueryHandler(lambda u,c: _callback(u,c,B), group=-60000) if False else CallbackQueryHandler(lambda u,c:_callback(u,c,B)), group=-60000)
    app.add_handler(MessageHandler(filters.ALL, lambda u,c:_message(u,c,B)), group=-59999)
    B._absolute_access_owner_v1 = True
    log.info("ABSOLUTE ACCESS OWNER active: bot_enabled=0 blocks all non-admin callbacks/messages")
    return True
