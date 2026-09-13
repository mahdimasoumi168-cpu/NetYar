"""Final off-hours Telegram gate: only restart and registered partner login."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TZ = ZoneInfo("Asia/Tehran")
OPEN = time(7, 0)
CLOSE = time(19, 0)

def is_open():
    t = datetime.now(TZ).time()
    return OPEN <= t < CLOSE

def _markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])

def _closed_text():
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            "🕖 ساعت کاری: ۷ صبح تا ۷ شب به وقت تهران\n"
            "🌙 ساعت تعطیلی: ۷ شب تا ۷ صبح\n\n"
            "خدمات عادی در این ساعت غیرفعال است.\n"
            "برای ورود به پنل همکاران، شماره موبایل اختصاصی همکار باید از قبل در سیستم ثبت شده باشد.")

def _partner_login_state(B, uid):
    st = B.S.get(uid, {})
    return st.get("mode") in {"p_phone", "p_pass"}

def _registered_partner(B, uid):
    st = B.S.get(uid, {})
    pid = st.get("partner_id")
    if not pid: return False
    try:
        row = B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
        return bool(row)
    except Exception:
        return False

def _allowed_during_closed(B, uid):
    return bool(B.admin(uid) or _registered_partner(B, uid) or _partner_login_state(B, uid))

def install(app, B):
    if getattr(B, "_offhours_partner_gate_v3", False): return True

    async def cb(update, context):
        q = update.callback_query
        if not q: return
        data = str(q.data or "")
        if data not in {"off:restart", "off:partner"}: return
        uid = q.from_user.id
        await q.answer()
        if data == "off:restart":
            if not is_open() and not B.admin(uid):
                return await q.message.reply_text(_closed_text(), reply_markup=_markup())
            return await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))
        from telegram_partner_router_guard import _open_partner
        import telegram_ui_policy_v2 as UI
        return await _open_partner(update, context, B, UI)

    async def message_gate(update, context):
        if is_open(): return
        user = getattr(update, "effective_user", None)
        msg = getattr(update, "effective_message", None)
        if not user or not msg: return
        uid = user.id
        if _allowed_during_closed(B, uid): return
        await msg.reply_text(_closed_text(), reply_markup=_markup())
        raise ApplicationHandlerStop

    async def callback_gate(update, context):
        if is_open(): return
        q = getattr(update, "callback_query", None)
        if not q: return
        uid = q.from_user.id
        data = str(q.data or "")
        if data in {"off:restart", "off:partner"}: return
        if _allowed_during_closed(B, uid): return
        try: await q.answer("⏰ خارج از ساعت کاری است.", show_alert=True)
        except Exception: pass
        try: await q.message.reply_text(_closed_text(), reply_markup=_markup())
        finally: raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:(restart|partner)$"), group=-30000)
    app.add_handler(MessageHandler(filters.ALL, message_gate), group=-29999)
    app.add_handler(CallbackQueryHandler(callback_gate), group=-29998)
    B._offhours_partner_gate_v3 = True
    return True
