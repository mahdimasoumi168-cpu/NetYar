"""Final Telegram control layer.

Fixes the last routing seam by giving ik:* callbacks a highest-priority
handler, adds an admin-managed after-hours phone whitelist, and provides a
refresh button after each process/deploy for users who enter the bot.
"""
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.final_control")
TEHRAN = ZoneInfo("Asia/Tehran")
OPEN, CLOSE = time(7, 0), time(19, 0)
WHITELIST = "after_hours_phone:"
REFRESH = "🔄 به‌روزرسانی ربات"
DEPLOY_TEXT = "🔄 ربات به‌روزرسانی شده است.\nلطفاً دکمه پایین را بزنید تا ربات دوباره راه‌اندازی شود."


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


def _exempt(update, B):
    uid = getattr(getattr(update, "effective_user", None), "id", None)
    if uid is None: return False
    try:
        if B.admin(uid): return True
    except Exception: pass
    st = B.S.get(uid, {})
    if _white(B, st.get("phone")): return True
    pid = st.get("partner_id")
    if pid:
        try:
            r = B.db.conn.execute("SELECT phone FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
            if r and _white(B, r["phone"]): return True
        except Exception: pass
    return False


def _proxy(update, q, text):
    src = q.message
    class Msg:
        def __init__(self, original, value): self._original, self.text = original, value
        def __getattr__(self, name): return getattr(self._original, name)
    msg = Msg(src, text)
    return SimpleNamespace(update_id=getattr(update, "update_id", None), message=msg,
                           effective_message=msg, effective_user=q.from_user,
                           effective_chat=getattr(src, "chat", None), callback_query=q)


def _closed_markup(B, uid):
    rows = [[InlineKeyboardButton(REFRESH, callback_data="final:refresh")]]
    if B.admin(uid): rows.append([InlineKeyboardButton("🔷 پنل مدیریت بات", callback_data="final:admin")])
    return InlineKeyboardMarkup(rows)


def _closed_text():
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            "🕖 ساعت کاری: ۷ صبح تا ۷ شب\n"
            "🌙 از ساعت ۷ شب تا ۷ صبح ربات بسته است.\n\n"
            "لطفاً از ساعت ۷ صبح دوباره مراجعه کنید.")


async def _closed_callback(update, context, B):
    q = update.callback_query
    if not q or _open() or _exempt(update, B): return
    data = str(q.data or "")
    if data == "final:refresh":
        await q.answer()
        old = B.S.get(q.from_user.id, {})
        B.S[q.from_user.id] = {"lang": old.get("lang", "fa")}
        status = old.get("status") or old.get("citizenship")
        if status: B.S[q.from_user.id].update(status=status, citizenship=status)
        await B.start(_proxy(update, q, "/start"), context)
        raise ApplicationHandlerStop
    if data == "final:admin" and B.admin(q.from_user.id):
        await q.answer(); await B.router(_proxy(update, q, "🛠 پنل مدیریت بات"), context)
        raise ApplicationHandlerStop
    await q.answer("⏰ ربات خارج از ساعت کاری است.", show_alert=True)
    await q.message.reply_text(_closed_text(), reply_markup=_closed_markup(B, q.from_user.id))
    raise ApplicationHandlerStop


async def _closed_message(update, context, B):
    if _open() or _exempt(update, B): return
    msg = getattr(update, "effective_message", None)
    if not msg: return
    text = str(getattr(msg, "text", "") or "").strip()
    if _white(B, text): return
    if text == REFRESH:
        await B.start(update, context); raise ApplicationHandlerStop
    await msg.reply_text(_closed_text(), reply_markup=_closed_markup(B, getattr(getattr(update, "effective_user", None), "id", 0)))
    raise ApplicationHandlerStop


async def _click(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("ik:"): return
    await q.answer()
    try:
        import telegram_no_reply_keyboard as N
        label = str(N._ACTIONS.get(str(q.data)) or "").strip()
    except Exception: label = ""
    if not label:
        for row in getattr(getattr(q.message, "reply_markup", None), "inline_keyboard", []) or []:
            for b in row:
                if str(getattr(b, "callback_data", "")) == str(q.data): label = str(getattr(b, "text", "") or "").strip()
    for p in ("🟢 ", "🟠 ", "🟣 ", "🟡 ", "⚪ ", "🔷 "):
        if label.startswith(p): label = label[len(p):].strip(); break
    label = {
        "💳 ➕ شارژ حساب":"➕ شارژ حساب", "👥 Partner panel":"👥 پنل همکاران",
        "👥 لوحة الشركاء":"👥 پنل همکاران", "🎫 Tracking":"🎫 پیگیری",
        "🎫 المتابعة":"🎫 پیگیری", "🪪 FIDA service":"🪪 فیدای غیر حضوری",
        "🖨 Printing":"🖨 خدمات چاپ", "📱 SIM services":"📱 خدمات سیم کارت",
        "📞 Contact us":"📞 تماس با ما", "📝 Customer complaint":"📝 ثبت شکایت مشتریان",
        "✉️ Ticket to management":"✉️ تیکت به مدیریت",
    }.get(label, label)
    if label in {REFRESH, "🔄 شروع مجدد"}:
        old = B.S.get(q.from_user.id, {}); lang = old.get("lang", "fa"); status = old.get("status") or old.get("citizenship")
        B.S[q.from_user.id] = {"lang": lang}
        if status: B.S[q.from_user.id].update(status=status, citizenship=status)
        await B.start(_proxy(update, q, "/start"), context); raise ApplicationHandlerStop
    if not label:
        await q.message.reply_text("❌ این دکمه دیگر معتبر نیست؛ لطفاً از منوی فعلی استفاده کنید."); raise ApplicationHandlerStop
    try:
        await B.router(_proxy(update, q, label), context)
    except ApplicationHandlerStop: raise
    except Exception:
        log.exception("inline click failed: %s", label)
        await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
    raise ApplicationHandlerStop


def _color_kb(B, rows):
    # Telegram does not expose button background colours; these markers provide
    # the same visual grouping while keeping labels routable.
    return B.kb(rows)


def install(app, B):
    if getattr(B, "_final_control_layer", False): return
    # Keep the public menu grouped by colour markers. Blue is reserved for the
    # partner/admin entry points; Telegram itself cannot colour button chrome.
    old_main = B.main
    def main(uid):
        return _color_kb(B, [["🟢 🪪 فیدای غیر حضوری", "🟠 🖨 خدمات چاپ"],
            ["🟣 🪪 حل مشکل ورود اتباع دولت من", "🟡 🎫 کد رهگیری تمدید کارت‌ها"],
            ["🟠 📱 خدمات سیم کارت", "🟣 📝 آزمون غربالگری"],
            ["🟢 🎫 پیگیری", "🟡 💰 کیف پول من"],
            ["⚪ 📞 تماس با ما", "⚪ 📝 ثبت شکایت مشتریان"],
            ["🔷 👥 پنل همکاران"], [B.CANCEL], ["🔄 شروع مجدد"]])
    B.main = main
    if hasattr(B, "partner_kb"):
        B.partner_kb = lambda lang="fa": _color_kb(B, [["🔷 ➕ شارژ حساب", "🔷 🏛 حل مشکل سامانه دولت من"],
            ["🔷 🔎 پیگیری کد", "🔷 📋 سوابق"], ["🔷 💰 موجودی"], ["🔷 🚪 خروج از پنل"], [B.CANCEL]])

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

    app.add_handler(CallbackQueryHandler(lambda u,c: _closed_callback(u,c,B), pattern=r"^final:"), group=-2000)
    app.add_handler(MessageHandler(filters.ALL, lambda u,c: _closed_message(u,c,B),), group=-1999)
    app.add_handler(CallbackQueryHandler(lambda u,c: _click(u,c,B), pattern=r"^ik:"), group=-1998)

    seen = set()
    async def notice(update, context):
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        msg = getattr(update, "effective_message", None)
        if uid is None or uid in seen or getattr(update, "callback_query", None): return
        seen.add(uid)
        try: await msg.reply_text(DEPLOY_TEXT, reply_markup=_deploy_markup())
        except Exception: log.exception("deploy notice failed")
    def _deploy_markup(): return InlineKeyboardMarkup([[InlineKeyboardButton(REFRESH, callback_data="final:refresh")]])
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, notice), group=-1900)
    B._final_control_layer = True
