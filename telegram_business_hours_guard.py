"""Telegram business-hours gate for NetYar.

Public operating hours are 07:00 through 19:00 Tehran time. Administrators
and the designated permanent partner are never blocked by this gate.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TEHRAN = ZoneInfo("Asia/Tehran")
OPEN = time(7, 0)
CLOSE = time(19, 0)
PERMANENT_PARTNER_PHONE = "09999527639"


def is_open(now=None):
    current = (now or datetime.now(TEHRAN)).astimezone(TEHRAN).time()
    return OPEN <= current < CLOSE


def _uid(update):
    user = getattr(update, "effective_user", None)
    return getattr(user, "id", None)


def _is_exempt(update, B):
    uid = _uid(update)
    if uid is not None and B is not None:
        try:
            if B.admin(uid):
                return True
        except Exception:
            pass
        try:
            st = B.S.get(uid, {})
            phone = str(st.get("phone") or "").strip()
            if phone == PERMANENT_PARTNER_PHONE:
                return True
            pid = st.get("partner_id")
            if pid:
                row = B.db.conn.execute("SELECT phone FROM partners WHERE id=?", (pid,)).fetchone()
                if row and str(row["phone"]).strip() == PERMANENT_PARTNER_PHONE:
                    return True
            chat = B.db.setting(f"partner_chat_{PERMANENT_PARTNER_PHONE}", "").strip()
            if chat and str(uid) == chat:
                return True
        except Exception:
            pass
    return False


def closed_text():
    return (
        "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
        "🕖 ساعت کاری: ۷ صبح تا ۷ شب\n"
        "🌙 از ساعت ۷ شب تا ۷ صبح ربات بسته است.\n\n"
        "لطفاً از ساعت ۷ صبح دوباره مراجعه کنید."
    )


def install(app, B=None):
    if getattr(app, "_netyar_business_hours_guard", False):
        return

    async def block_message(update, context):
        if is_open() or _is_exempt(update, B):
            return
        message = getattr(update, "effective_message", None)
        if message:
            try:
                await message.reply_text(closed_text())
            finally:
                raise ApplicationHandlerStop
        raise ApplicationHandlerStop

    async def block_callback(update, context):
        if is_open() or _is_exempt(update, B):
            return
        q = getattr(update, "callback_query", None)
        if q:
            try:
                await q.answer("⏰ ربات خارج از ساعت کاری است.", show_alert=True)
            except Exception:
                pass
            try:
                await q.message.reply_text(closed_text())
            finally:
                raise ApplicationHandlerStop
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(block_callback), group=-100000)
    app.add_handler(MessageHandler(filters.ALL, block_message), group=-100001)
    app._netyar_business_hours_guard = True
