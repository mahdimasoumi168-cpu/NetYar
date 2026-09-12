"""Final Telegram control layer: deterministic callbacks + business-hours gate."""
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.final_control")
TEHRAN = ZoneInfo("Asia/Tehran")
OPEN, CLOSE = time(7, 0), time(19, 0)
PERMANENT_PARTNER_PHONE = "09999527639"
WHITELIST = "after_hours_phone:"
REFRESH = "🔄 شروع مجدد"

def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

def _phone(v):
    s = _digits(v).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if s.startswith("+98"): s = "0" + s[3:]
    elif s.startswith("0098"): s = "0" + s[4:]
    return s if len(s) == 11 and s.startswith("09") and s.isdigit() else None

def _open():
    t = datetime.now(TEHRAN).time()
    return OPEN <= t < CLOSE

def _white(B, phone):
    p = _phone(phone)
    if not p: return False
    try: return B.db.setting(WHITELIST + p, "") == "1"
    except Exception: return False

def _permanent_partner(B, uid):
    try:
        st = B.S.get(uid, {})
        if _phone(st.get("phone")) == PERMANENT_PARTNER_PHONE: return True
        pid = st.get("partner_id")
        if pid:
            r = B.db.conn.execute("SELECT phone FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
            if r and _phone(r["phone"]) == PERMANENT_PARTNER_PHONE: return True
    except Exception: pass
    return False

def _exempt(update, B):
    uid = getattr(getattr(update, "effective_user", None), "id", None)
    if uid is None: return False
    try:
        if B.admin(uid): return True
    except Exception: pass
    st = B.S.get(uid, {})
    return _permanent_partner(B, uid) or _white(B, st.get("phone"))

def _proxy(update, q, text):
    src = q.message
    class Msg:
        def __init__(self, original, value): self._original, self.text = original, value
        def __getattr__(self, name): return getattr(self._original, name)
    msg = Msg(src, text)
    return SimpleNamespace(update_id=getattr(update, "update_id", None), message=msg, effective_message=msg, effective_user=q.from_user, effective_chat=getattr(src, "chat", None), callback_query=q)

def _closed_text():
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            "🕖 ساعت کاری: ۷ صبح تا ۷ شب\n"
            "🌙 از ساعت ۷ شب تا ۷ صبح ربات بسته است.\n\n"
            "لطفاً در ساعت کاری دوباره مراجعه کنید.")

def _closed_markup(B, uid):
    rows = [[InlineKeyboardButton(REFRESH, callback_data="final:refresh")]]
    if _permanent_partner(B, uid): rows.insert(0, [InlineKeyboardButton("👥 پنل همکاران", callback_data="final:partner")])
    elif B.admin(uid): rows.insert(0, [InlineKeyboardButton("🛠 پنل مدیریت بات", callback_data="final:admin")])
    return InlineKeyboardMarkup(rows)

async def _show_closed(update, context, B, uid):
    await update.effective_message.reply_text(_closed_text(), reply_markup=_closed_markup(B, uid))

async def _closed_callback(update, context, B):
    q = update.callback_query
    if not q: return
    data = str(q.data or "")
    if _open() or _exempt(update, B):
        if data == "final:partner" and _permanent_partner(B, q.from_user.id):
            await q.answer(); await B.partner(_proxy(update, q, "👥 پنل همکاران"), context); raise ApplicationHandlerStop
        if data == "final:admin" and B.admin(q.from_user.id):
            await q.answer(); fn = getattr(B, "admin_text", None)
            if fn: await fn(_proxy(update, q, "🛠 پنل مدیریت بات"), context)
            else: await q.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            raise ApplicationHandlerStop
        return
    if data == "final:refresh":
        await q.answer()
        old = dict(B.S.get(q.from_user.id, {}))
        if _open(): await B.start(_proxy(update, q, "/start"), context)
        else:
            B.S[q.from_user.id] = {"lang": old.get("lang", "fa")}
            status = old.get("status") or old.get("citizenship")
            if status: B.S[q.from_user.id].update(status=status, citizenship=status)
            await _show_closed(update, context, B, q.from_user.id)
        raise ApplicationHandlerStop
    if data == "final:partner" and _permanent_partner(B, q.from_user.id):
        await q.answer(); await B.partner(_proxy(update, q, "👥 پنل همکاران"), context); raise ApplicationHandlerStop
    if data == "final:admin" and B.admin(q.from_user.id):
        await q.answer(); fn = getattr(B, "admin_text", None)
        if fn: await fn(_proxy(update, q, "🛠 پنل مدیریت بات"), context)
        else: await q.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
        raise ApplicationHandlerStop
    try: await q.answer("⏰ ربات خارج از ساعت کاری است.", show_alert=True)
    except Exception: pass
    await _show_closed(update, context, B, q.from_user.id)
    raise ApplicationHandlerStop

async def _closed_message(update, context, B):
    if _open() or _exempt(update, B): return
    msg = getattr(update, "effective_message", None)
    if not msg: return
    text = str(getattr(msg, "text", "") or "").strip()
    if text in {REFRESH, "🔄 شروع مجدد"}:
        if _open(): await B.start(update, context)
        else: await _show_closed(update, context, B, getattr(getattr(update, "effective_user", None), "id", 0))
        raise ApplicationHandlerStop
    await msg.reply_text(_closed_text(), reply_markup=_closed_markup(B, getattr(getattr(update, "effective_user", None), "id", 0)))
    raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, "_final_control_layer", False): return
    app.add_handler(CallbackQueryHandler(lambda u,c: _closed_callback(u,c,B), pattern=r"^final:"), group=-2000)
    app.add_handler(MessageHandler(filters.ALL, lambda u,c: _closed_message(u,c,B)), group=-1999)
    old_admin = getattr(B, "admin_text", None)
    if old_admin:
        async def admin_text(update, context):
            uid = update.effective_user.id; st = B.S.setdefault(uid, {}); t = str(getattr(update.message, "text", "") or "").strip()
            if B.admin(uid) and t in {"⏰ مجاز خارج از ساعت بسته بودن", "🔷 ⏰ مجاز خارج از ساعت بسته بودن"}:
                st["mode"] = "after_hours_phone"
                return await update.message.reply_text("📱 شماره موبایلی را وارد کنید که خارج از ساعت بسته بودن هم مجاز باشد:\nمثال: 09123456789", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            if B.admin(uid) and st.get("mode") == "after_hours_phone":
                p = _phone(t)
                if not p: return await update.message.reply_text("❌ شماره موبایل معتبر نیست.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
                B.db.set_setting(WHITELIST + p, "1"); st["mode"] = "cc_menu"
                return await update.message.reply_text("✅ شماره ثبت شد و از این به بعد خارج از ساعت بسته بودن هم مجاز است.", reply_markup=B.kb([["🔷 ⏰ مجاز خارج از ساعت بسته بودن"], ["⬅️ منوی اصلی"]]))
            return await old_admin(update, context)
        B.admin_text = admin_text
    B._final_control_layer = True
    log.info("Final Telegram business-hours control installed")
