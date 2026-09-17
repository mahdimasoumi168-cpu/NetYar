"""Canonical Telegram off-hours gate with persistent night-worker sessions.

Single source of truth for working-hours state. The global setting
``night_shift_enabled`` controls whether off-hours are open to the explicitly
allowed night-shift partner path. All other modules import this function, so
changing the setting never depends on late monkey-patching or stale closures.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TZ = ZoneInfo("Asia/Tehran")
DEFAULT_OPEN = "07:00"
DEFAULT_CLOSE = "19:00"
PREFIX = "night_worker:"
NIGHT_KEY = "night_shift_enabled"
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"


def normalize_phone(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def _setting(B, key, default):
    try:
        return str(B.db.setting(key, default) or default)
    except Exception:
        return default


def night_shift_enabled(B):
    """Return the persistent global night-access switch.

    Missing legacy rows intentionally default to enabled so existing installs
    keep their previous behaviour until an administrator explicitly closes the
    night access switch.
    """
    return _setting(B, NIGHT_KEY, "1") == "1"


def _clock_is_open(B):
    op = _setting(B, "work_open", DEFAULT_OPEN)
    cl = _setting(B, "work_close", DEFAULT_CLOSE)
    try:
        o = time.fromisoformat(op)
        c = time.fromisoformat(cl)
        now = datetime.now(TZ).time()
        return o <= now < c if o < c else (now >= o or now < c)
    except Exception:
        return False


def _is_open(B):
    """Canonical effective availability used by every Telegram gate.

    During 07:00-19:00 it is always open. Outside those hours the administrator
    night switch decides whether the bot is globally open. This function is
    deliberately stable and is never replaced at runtime, avoiding stale
    imported-function closures in other guards.
    """
    if _clock_is_open(B):
        return True
    return night_shift_enabled(B)


def _partner_by_phone(B, phone):
    phone = normalize_phone(phone)
    try:
        rows = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
        for row in rows:
            if normalize_phone(row["phone"]) == phone:
                return row
    except Exception:
        return None
    return None


def _active_partner_session(B, uid):
    st = B.S.get(uid, {}) or {}
    if st.get("partner_logged_out"):
        return None
    pid = st.get("partner_id")
    if not pid or st.get("partner_active") is not True:
        return None
    try:
        return B.db.conn.execute(
            "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)
        ).fetchone()
    except Exception:
        return None


def is_night_worker(B, uid):
    row = _active_partner_session(B, uid)
    if row:
        try:
            return str(B.db.setting(PREFIX + str(row["id"]), "0")) == "1"
        except Exception:
            return False
    st = B.S.get(uid, {}) or {}
    pid = st.get("partner_id")
    try:
        if pid and str(B.db.setting(PREFIX + str(pid), "0")) == "1":
            row = B.db.conn.execute(
                "SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)
            ).fetchone()
            return bool(row)
        phone = normalize_phone(st.get("phone") or st.get("partner_phone"))
        if phone:
            row = _partner_by_phone(B, phone)
            return bool(row and str(B.db.setting(PREFIX + str(row["id"]), "0")) == "1")
    except Exception:
        return False
    return False


def _allowed_during_closed(B, uid):
    return bool(is_night_worker(B, uid))


def _closed_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])


def _closed_text(B):
    op = _setting(B, "work_open", DEFAULT_OPEN)
    cl = _setting(B, "work_close", DEFAULT_CLOSE)
    return (
        "❌ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
        f"🕖 ساعت کاری: {op} تا {cl} به وقت تهران\n"
        "🚫 هیچ‌یک از خدمات عمومی، دریافت اطلاعات یا شروع درخواست در این زمان مجاز نیست.\n\n"
        "برای شیفت شب فقط همکارانی که در پنل مدیریت برای شیفت شب تعریف شده‌اند\n"
        "می‌توانند از مسیر «👥 پنل همکاران» وارد شوند."
    )


def _night_login_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="off:restart")]])


def _night_partner_markup(B, uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([
            ["➕ شارژ حساب", IRANCELL],
            ["🏛 حل مشکل سامانه دولت من", "🎫 درخواست‌های من"],
            ["📱 خدمات سیم کارت", "🪪 فیدای غیر حضوری"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی"],
            ["🎫 تیکت به مدیریت", "💬 ارتباط با مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)
    except Exception:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ شارژ حساب", callback_data="__never__")],
            [InlineKeyboardButton(IRANCELL, callback_data="__never__")],
            [InlineKeyboardButton("🏛 حل مشکل سامانه دولت من", callback_data="__never__")],
            [InlineKeyboardButton("🎫 درخواست‌های من", callback_data="__never__")],
            [InlineKeyboardButton("📱 خدمات سیم کارت", callback_data="__never__")],
            [InlineKeyboardButton("🪪 فیدای غیر حضوری", callback_data="__never__")],
            [InlineKeyboardButton("🔎 پیگیری کد", callback_data="__never__")],
            [InlineKeyboardButton("📋 سوابق", callback_data="__never__")],
            [InlineKeyboardButton("💰 موجودی", callback_data="__never__")],
            [InlineKeyboardButton("🎫 تیکت به مدیریت", callback_data="__never__")],
            [InlineKeyboardButton("💬 ارتباط با مدیریت", callback_data="__never__")],
            [InlineKeyboardButton("🚪 خروج از پنل", callback_data="__never__")],
            [InlineKeyboardButton("❌ انصراف", callback_data="__never__")],
        ])


def install(app, B):
    if getattr(B, "_offhours_partner_gate_v7", False):
        return True

    async def cb(update, context):
        q = update.callback_query
        if not q:
            return
        data = str(q.data or "")
        if data not in {"off:restart", "off:partner"}:
            return
        try:
            await q.answer()
        except Exception:
            pass
        uid = q.from_user.id

        if data == "off:restart":
            if not _is_open(B):
                await q.message.reply_text(_closed_text(B), reply_markup=_closed_markup())
                raise ApplicationHandlerStop
            await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

        active = _active_partner_session(B, uid)
        if not _is_open(B):
            if active and is_night_worker(B, uid):
                await q.message.reply_text("🌙 پنل همکاران شیفت شب فعال است.", reply_markup=_night_partner_markup(B, uid))
                raise ApplicationHandlerStop
            st = B.S.setdefault(uid, {})
            for k in ("partner_id", "partner_active", "partner", "partner_phone", "phone"):
                st.pop(k, None)
            st["partner_logged_out"] = True
            st["mode"] = "night_phone"
            st["step"] = "night_phone"
            await q.message.reply_text(
                "🌙 ورود به پنل همکاران شیفت شب\n\n"
                "🔐 برای ورود باید دوباره اطلاعات همکار را وارد کنید.\n\n"
                "📱 شماره موبایل اختصاصی همکار را وارد کنید:",
                reply_markup=_night_login_markup(),
            )
            raise ApplicationHandlerStop

        from telegram_partner_router_guard import _open_partner
        import telegram_ui_policy_v2 as UI
        await _open_partner(update, context, B, UI)
        raise ApplicationHandlerStop

    async def night_login(update, context):
        if not update.effective_user or not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if mode not in {"night_phone", "night_pass"}:
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        if _is_open(B):
            st["mode"] = None
            st["step"] = None
            return
        if mode == "night_phone":
            phone = normalize_phone(text)
            if not re.fullmatch(r"09\d{9}", phone):
                await update.message.reply_text("❌ شماره موبایل صحیح نیست. دوباره وارد کنید:")
                raise ApplicationHandlerStop
            partner = _partner_by_phone(B, phone)
            if not partner:
                await update.message.reply_text("❌ این شماره به همکار فعال اختصاص ندارد.\n\n📱 شماره را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            pid = partner["id"]
            if str(B.db.setting(PREFIX + str(pid), "0")) != "1":
                st["mode"] = None
                st["step"] = None
                await update.message.reply_text("❌ این شماره برای شیفت شب مجاز نیست.")
                raise ApplicationHandlerStop
            st["night_phone"] = phone
            st["night_partner_id"] = pid
            st["mode"] = "night_pass"
            st["step"] = "night_pass"
            await update.message.reply_text("🔐 رمز عبور همکار را وارد کنید:")
            raise ApplicationHandlerStop
        phone = normalize_phone(st.get("night_phone"))
        partner = _partner_by_phone(B, phone)
        if not partner or str(B.db.setting(PREFIX + str(partner["id"]), "0")) != "1":
            st["mode"] = None
            st["step"] = None
            await update.message.reply_text("❌ دسترسی شیفت شب تأیید نشد.")
            raise ApplicationHandlerStop
        try:
            from core import check_password
            ok = bool(check_password(text, partner["password_hash"]))
        except Exception:
            ok = False
        if not ok:
            st["mode"] = "night_pass"
            st["step"] = "night_pass"
            await update.message.reply_text("❌ رمز عبور نادرست است.\n\n🔐 رمز عبور را دوباره وارد کنید:")
            raise ApplicationHandlerStop
        st["partner"] = phone
        st["partner_phone"] = phone
        st["partner_id"] = partner["id"]
        st["partner_active"] = True
        st["partner_logged_out"] = False
        st["mode"] = "partner"
        st["step"] = None
        try:
            markup = _night_partner_markup(B, uid)
        except Exception:
            markup = B.partner_kb("fa")
        await update.message.reply_text("✅ ورود همکار برای شیفت شب با موفقیت انجام شد.", reply_markup=markup)
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:(restart|partner)$"), group=-30000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, night_login), group=-29999)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: None), group=-29998)
    app.add_handler(CallbackQueryHandler(lambda u, c: None, pattern=r"^off:"), group=-29997)
    B._offhours_partner_gate_v7 = True
    return True
