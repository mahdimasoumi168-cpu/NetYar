"""Absolute customer off-hours guard.

Runs before normal Telegram routing. Ordinary users cannot start, continue,
or trigger any customer flow outside configured working hours. Night-worker
login is the only customer-side exception until authentication succeeds.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram.ext import MessageHandler, CallbackQueryHandler, TypeHandler, ApplicationHandlerStop, filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

TZ = ZoneInfo("Asia/Tehran")
DEFAULT_OPEN = "07:00"
DEFAULT_CLOSE = "19:00"


def _setting(B, key, default):
    try:
        return str(B.db.setting(key, default) or default)
    except Exception:
        return default


def is_open(B):
    try:
        o = time.fromisoformat(_setting(B, "work_open", DEFAULT_OPEN))
        c = time.fromisoformat(_setting(B, "work_close", DEFAULT_CLOSE))
        now = datetime.now(TZ).time()
        return o <= now < c if o < c else (now >= o or now < c)
    except Exception:
        return False


def night_worker(B, uid):
    try:
        st = B.S.get(uid, {}) or {}
        pid = st.get("partner_id")
        if pid and st.get("partner_active") and not st.get("partner_logged_out"):
            row = B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
            return bool(row and str(B.db.setting("night_worker:" + str(row["id"]), "0")) == "1")
        phone = st.get("phone") or st.get("partner_phone")
        if phone:
            digits = str(phone).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace("+98", "0", 1)
            row = B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1 LIMIT 1", (digits,)).fetchone()
            return bool(row and str(B.db.setting("night_worker:" + str(row["id"]), "0")) == "1")
    except Exception:
        return False
    return False


def closed_text(B):
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            f"🕖 ساعت کاری: {_setting(B, 'work_open', DEFAULT_OPEN)} تا {_setting(B, 'work_close', DEFAULT_CLOSE)} به وقت تهران\n\n"
            "🚫 در این زمان هیچ خدماتی، دریافت اطلاعات یا ادامه درخواست فعال نیست.")


def markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])


def install(app, B):
    if getattr(B, "_absolute_offhours_guard_v1", False):
        return

    async def gate(update, context):
        if is_open(B):
            return
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        if uid is None or B.admin(uid) or night_worker(B, uid):
            return
        msg = getattr(update, "effective_message", None)
        if not msg:
            return
        st = B.S.get(uid, {}) or {}
        # Allow only the credential collection that was explicitly opened by
        # the off-hours partner button. It still verifies night-worker status.
        if st.get("mode") in {"night_phone", "night_pass"}:
            return
        txt = str(getattr(msg, "text", "") or "").strip()
        if txt in {"🔄 شروع مجدد", "شروع مجدد", "/restart"}:
            return
        await msg.reply_text(closed_text(B), reply_markup=markup())
        raise ApplicationHandlerStop

    async def callback_gate(update, context):
        if is_open(B):
            return
        q = getattr(update, "callback_query", None)
        if not q:
            return
        uid = q.from_user.id
        if B.admin(uid) or night_worker(B, uid):
            return
        data = str(q.data or "")
        # These are handled by the dedicated off-hours/night-worker gate.
        if data in {"off:restart", "off:partner"}:
            return
        try:
            await q.answer("⏰ خارج از ساعت کاری است.", show_alert=True)
        except Exception:
            pass
        await q.message.reply_text(closed_text(B), reply_markup=markup())
        raise ApplicationHandlerStop

    # TypeHandler is intentionally the earliest possible guard, before the
    # canonical startup callback can open a menu while the bot is closed.
    async def update_gate(update, context):
        if is_open(B):
            return
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        if uid is None or B.admin(uid) or night_worker(B, uid):
            return
        data = str(getattr(getattr(update, "callback_query", None), "data", "") or "")
        if data in {"off:restart", "off:partner"}:
            return
        # Do not duplicate the response; the message/callback gate will do it.
        return

    app.add_handler(TypeHandler(__import__("telegram").Update, update_gate), group=-2000000)
    app.add_handler(CallbackQueryHandler(callback_gate), group=-1999999)
    app.add_handler(MessageHandler(filters.ALL, gate), group=-1999998)
    B._absolute_offhours_guard_v1 = True
