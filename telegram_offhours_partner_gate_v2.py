"""Final Telegram off-hours gate with explicit night-worker access.
Outside normal hours, ordinary users and ordinary partners are blocked.
Only admins and partners explicitly marked night_worker:<partner_id>=1 may use the bot.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TZ = ZoneInfo("Asia/Tehran")
OPEN = time(7, 0)
CLOSE = time(19, 0)
PREFIX = "night_worker:"

def is_open():
    return OPEN <= datetime.now(TZ).time() < CLOSE

def is_night_worker(B, uid):
    st = B.S.get(uid, {})
    pid = st.get("partner_id")
    try:
        if pid and B.db.setting(PREFIX + str(pid), "0") == "1":
            row = B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            return bool(row)
        phone = str(st.get("phone") or "").strip()
        if phone:
            row = B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1 LIMIT 1", (phone,)).fetchone()
            return bool(row and B.db.setting(PREFIX + str(row["id"]), "0") == "1")
    except Exception:
        return False
    return False

def _allowed_during_closed(B, uid):
    # IMPORTANT: being a normal/previously logged-in partner is NOT enough.
    # Outside hours only admins and explicitly configured night workers pass.
    return bool(B.admin(uid) or is_night_worker(B, uid))

def _markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])

def _closed_text():
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            "🕖 ساعت کاری عادی: ۷ صبح تا ۷ شب به وقت تهران\n"
            "🌙 خدمات عادی در این زمان غیرفعال است.\n\n"
            "فقط همکارانی که قبلاً برای شیفت شب تعریف شده‌اند می‌توانند وارد پنل همکاران شوند.")

def install(app, B):
    if getattr(B, "_offhours_partner_gate_v4", False):
        return True

    async def cb(update, context):
        q = update.callback_query
        if not q: return
        data = str(q.data or "")
        if data not in {"off:restart", "off:partner"}: return
        await q.answer()
        uid = q.from_user.id
        if data == "off:restart":
            if not is_open() and not _allowed_during_closed(B, uid):
                return await q.message.reply_text(_closed_text(), reply_markup=_markup())
            return await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))
        from telegram_partner_router_guard import _open_partner
        import telegram_ui_policy_v2 as UI
        if not is_open() and not _allowed_during_closed(B, uid):
            return await q.message.reply_text(_closed_text(), reply_markup=_markup())
        return await _open_partner(update, context, B, UI)

    async def message_gate(update, context):
        if is_open(): return
        user = getattr(update, "effective_user", None); msg = getattr(update, "effective_message", None)
        if not user or not msg: return
        if _allowed_during_closed(B, user.id): return
        await msg.reply_text(_closed_text(), reply_markup=_markup())
        raise ApplicationHandlerStop

    async def callback_gate(update, context):
        if is_open(): return
        q = getattr(update, "callback_query", None)
        if not q: return
        uid = q.from_user.id; data = str(q.data or "")
        if data in {"off:restart", "off:partner"} or _allowed_during_closed(B, uid): return
        try: await q.answer("⏰ خارج از ساعت کاری است.", show_alert=True)
        except Exception: pass
        try: await q.message.reply_text(_closed_text(), reply_markup=_markup())
        finally: raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:(restart|partner)$"), group=-30000)
    app.add_handler(MessageHandler(filters.ALL, message_gate), group=-29999)
    app.add_handler(CallbackQueryHandler(callback_gate), group=-29998)
    B._offhours_partner_gate_v4 = True
    return True
