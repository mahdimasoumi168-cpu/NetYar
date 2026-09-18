"""Canonical Telegram off-hours gate.

Public/customer access follows business hours only. The persistent
``night_shift_enabled`` switch controls only the explicitly whitelisted
night-worker partner path outside 07:00-19:00 Tehran time.
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
NIGHT_PUBLIC_KEY = "night_public_open"
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
    return _setting(B, NIGHT_KEY, "1") == "1"


def night_public_open(B):
    return _setting(B, NIGHT_PUBLIC_KEY, "0") == "1"


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
    """Public/customer availability: normal hours OR explicit night-open switch."""
    return bool(_clock_is_open(B) or night_public_open(B))


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
        return B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
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
            return bool(B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone())
        phone = normalize_phone(st.get("phone") or st.get("partner_phone"))
        if phone:
            row = _partner_by_phone(B, phone)
            return bool(row and str(B.db.setting(PREFIX + str(row["id"]), "0")) == "1")
    except Exception:
        return False
    return False


def _allowed_during_closed(B, uid):
    """Return whether this account may use the night-partner entry path.
    This does not authenticate the partner; it only permits the login screen.
    """
    try:
        if B.admin(uid):
            return True
    except Exception:
        pass
    if not night_shift_enabled(B):
        return False
    if is_night_worker(B, uid):
        return True
    # After a real logout, the in-memory session is intentionally empty.
    # Use the persistent partner<->Telegram link only to allow the fresh
    # phone/password login screen; never grant an authenticated session.
    try:
        row=B.db.conn.execute(
            "SELECT p.id FROM partners p JOIN partner_telegram_links l ON l.partner_id=p.id "
            "WHERE p.active=1 AND l.telegram_user_id=? LIMIT 1",(str(uid),)
        ).fetchone()
        if row and str(B.db.setting(PREFIX+str(row["id"]),"0"))=="1":
            return True
    except Exception:
        pass
    return False

def night_access_open(B, uid):
    try:
        if _clock_is_open(B) or night_public_open(B): return True
        if B.admin(uid): return True
    except Exception: pass
    return bool(night_shift_enabled(B) and is_night_worker(B, uid))


def _closed_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])


def _closed_text(B):
    op = _setting(B, "work_open", DEFAULT_OPEN)
    cl = _setting(B, "work_close", DEFAULT_CLOSE)
    return ("❌ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            f"🕖 ساعت کاری: {op} تا {cl} به وقت تهران\n"
            "🚫 خدمات عمومی، دریافت اطلاعات و شروع درخواست در این زمان مجاز نیست.\n\n"
            "برای شیفت شب فقط همکارانی که در پنل مدیریت مجاز شده‌اند می‌توانند وارد شوند.")


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
        return B.partner_kb("fa")


def install(app, B):
    if getattr(B, "_offhours_partner_gate_v9", False):
        return True

    old_main = getattr(B, "main", None)
    if callable(old_main) and not getattr(B, "_night_main_guard_v1", False):
        def guarded_main(uid, *args, **kwargs):
            try:
                if not _clock_is_open(B) and not B.admin(uid):
                    if night_shift_enabled(B) and is_night_worker(B, uid):
                        return _night_partner_markup(B, uid)
                    return _closed_markup()
            except Exception:
                return _closed_markup()
            return old_main(uid, *args, **kwargs)
        B.main = guarded_main
        B._night_main_guard_v1 = True

    async def cb(update, context):
        q = update.callback_query
        if not q or str(q.data or "") not in {"off:restart", "off:partner"}:
            return
        try:
            await q.answer()
        except Exception:
            pass
        uid = q.from_user.id

        if q.data == "off:restart":
            if not _is_open(B):
                await q.message.reply_text(_closed_text(B), reply_markup=_closed_markup())
                raise ApplicationHandlerStop
            await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

        # Partner entry is allowed after hours only when the global night switch
        # is ON and this partner is explicitly whitelisted.
        if not _is_open(B):
            if not night_shift_enabled(B):
                await q.message.reply_text(
                    "🌙 شیفت شب در حال حاضر بسته است.\n\n"
                    "دسترسی خارج از ساعت کاری توسط مدیریت بسته شده است.",
                    reply_markup=_closed_markup(),
                )
                raise ApplicationHandlerStop
            active = _active_partner_session(B, uid)
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
                "🔐 برای ورود باید اطلاعات همکار را وارد کنید.\n\n"
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
        if not night_shift_enabled(B):
            st["mode"] = None
            st["step"] = None
            await update.message.reply_text("🌙 شیفت شب توسط مدیریت بسته شده است.", reply_markup=_closed_markup())
            raise ApplicationHandlerStop

        if mode == "night_phone":
            phone = normalize_phone(text)
            if not re.fullmatch(r"09\d{9}", phone):
                await update.message.reply_text("❌ شماره موبایل صحیح نیست. دوباره وارد کنید:")
                raise ApplicationHandlerStop
            partner = _partner_by_phone(B, phone)
            if not partner:
                # Unknown phone => canonical membership request. It must not
                # be treated as a failed login or granted night access.
                st["phone"] = phone
                st["partner_phone"] = phone
                st["partner_logged_out"] = True
                st["partner_active"] = False
                st["mode"] = "partner_new_wait"
                st["step"] = "partner_new_wait"
                try:
                    from telegram_partner_registration import _new_member
                    await _new_member(update, B)
                except Exception:
                    log.exception("night membership entry failed")
                    await update.message.reply_text(
                        "👤 این شماره هنوز همکار فعال نیست.\n\n"
                        "برای عضویت جدید از گزینه «🤝 درخواست عضویت» استفاده کنید."
                    )
                raise ApplicationHandlerStop
            pid = partner["id"]
            if str(B.db.setting(PREFIX + str(pid), "0")) != "1":
                st["mode"] = None; st["step"] = None
                await update.message.reply_text(
                    "❌ این شماره همکار فعال است، اما برای شیفت شب مجاز نشده است.\n\n"
                    "مدیریت باید این همکار را از بخش «🌙 همکاران شب‌کار» فعال کند.",
                    reply_markup=_closed_markup()
                )
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
            st["mode"] = None; st["step"] = None
            await update.message.reply_text("❌ دسترسی شیفت شب تأیید نشد.", reply_markup=_closed_markup())
            raise ApplicationHandlerStop
        try:
            from core import check_password
            ok = bool(check_password(text, partner["password_hash"]))
        except Exception:
            ok = False
        if not ok:
            st["mode"] = "night_pass"; st["step"] = "night_pass"
            await update.message.reply_text("❌ رمز عبور نادرست است.\n\n🔐 رمز عبور را دوباره وارد کنید:")
            raise ApplicationHandlerStop
        st["partner"] = phone; st["partner_phone"] = phone; st["partner_id"] = partner["id"]
        st["partner_active"] = True; st["partner_logged_out"] = False
        st["mode"] = "partner"; st["step"] = None
        await update.message.reply_text("✅ ورود همکار برای شیفت شب با موفقیت انجام شد.", reply_markup=_night_partner_markup(B, uid))
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:(restart|partner)$"), group=-30000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, night_login), group=-29999)
    app.add_handler(CallbackQueryHandler(lambda u, c: None, pattern=r"^off:"), group=-29997)
    B._offhours_partner_gate_v9 = True
    return True
