"""Final Telegram off-hours gate with persistent night-worker sessions.

Night-shift partners authenticate once. An already authenticated, active partner
session remains valid while the bot is running; inactivity must not silently
turn a valid session into a fake "please log in again" state.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TZ = ZoneInfo("Asia/Tehran")
OPEN = time(7, 0)
CLOSE = time(19, 0)
PREFIX = "night_worker:"


def normalize_phone(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def is_open():
    return OPEN <= datetime.now(TZ).time() < CLOSE


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
    """Return the active partner row for an already authenticated session."""
    st = B.S.get(uid, {}) or {}
    pid = st.get("partner_id")
    if not pid or st.get("partner_active") is False or st.get("partner_logged_out"):
        return None
    try:
        return B.db.conn.execute(
            "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)
        ).fetchone()
    except Exception:
        return None


def is_night_worker(B, uid):
    # A valid authenticated partner session is sufficient. Do not require a
    # second session lookup/refresh after inactivity; this was the source of
    # the night-shift "please log in again" behaviour.
    row = _active_partner_session(B, uid)
    if row:
        return True

    st = B.S.get(uid, {}) or {}
    pid = st.get("partner_id")
    try:
        if pid and B.db.setting(PREFIX + str(pid), "0") == "1":
            row = B.db.conn.execute(
                "SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)
            ).fetchone()
            return bool(row)
        phone = normalize_phone(st.get("phone") or st.get("partner_phone"))
        if phone:
            row = _partner_by_phone(B, phone)
            return bool(row and B.db.setting(PREFIX + str(row["id"]), "0") == "1")
    except Exception:
        return False
    return False


def _allowed_during_closed(B, uid):
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
            "فقط همکارانی که برای شیفت شب تعریف شده‌اند می‌توانند وارد پنل همکاران شوند.")


def _night_login_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="off:restart")]])


def install(app, B):
    if getattr(B, "_offhours_partner_gate_v5", False):
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
            if not is_open() and not _allowed_during_closed(B, uid):
                await q.message.reply_text(_closed_text(), reply_markup=_markup())
                raise ApplicationHandlerStop
            await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

        # Keep a valid night-shift session alive. Only request credentials when
        # there is no active partner session or the partner account is invalid.
        active = _active_partner_session(B, uid)
        if not is_open() and active:
            try:
                import telegram_ui_policy_v2 as UI
                markup = UI.inline([
                    ["➕ شارژ حساب", "🔎 پیگیری کد"],
                    ["📋 سوابق", "💰 موجودی"],
                    ["🏛 حل مشکل سامانه دولت من"],
                    ["💬 ارتباط با مدیریت"],
                    ["🚪 خروج از پنل"],
                ], B, uid)
            except Exception:
                markup = B.partner_kb("fa")
            await q.message.reply_text("🌙 پنل همکاران شیفت شب فعال است.", reply_markup=markup)
            raise ApplicationHandlerStop

        if not is_open():
            if B.admin(uid):
                from telegram_partner_router_guard import _open_partner
                import telegram_ui_policy_v2 as UI
                await _open_partner(update, context, B, UI)
                raise ApplicationHandlerStop
            st = B.S.setdefault(uid, {})
            st.pop("partner_id", None)
            st.pop("partner_active", None)
            st.pop("partner", None)
            st["mode"] = "night_phone"
            st["step"] = "night_phone"
            await q.message.reply_text(
                "🌙 ورود به پنل همکاران در شیفت شب\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
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
        st["step"] = "partner"
        st.pop("night_phone", None)
        st.pop("night_partner_id", None)
        try:
            B.db.set_setting(f"partner_chat_{phone}", str(uid))
            B.db.set_setting(f"partner_chat_{partner['id']}", str(uid))
        except Exception:
            pass
        try:
            import telegram_ui_policy_v2 as UI
            markup = UI.inline([
                ["➕ شارژ حساب", "🔎 پیگیری کد"],
                ["📋 سوابق", "💰 موجودی"],
                ["🏛 حل مشکل سامانه دولت من"],
                ["💬 ارتباط با مدیریت"],
                ["🚪 خروج از پنل"],
            ], B, uid)
        except Exception:
            markup = None
        await update.message.reply_text(
            f"🌙 ورود شیفت شب با موفقیت انجام شد.\n\n👤 {partner['name'] or '-'}\n📱 {phone}\n💰 اعتبار: {int(partner['balance'] or 0):,} تومان",
            reply_markup=markup,
        )
        raise ApplicationHandlerStop

    async def callback_gate(update, context):
        if is_open():
            return
        q = getattr(update, "callback_query", None)
        if not q:
            return
        uid = q.from_user.id
        data = str(q.data or "")
        if data in {"off:restart", "off:partner"} or _allowed_during_closed(B, uid):
            return
        try:
            await q.answer("⏰ خارج از ساعت کاری است.", show_alert=True)
        except Exception:
            pass
        try:
            await q.message.reply_text(_closed_text(), reply_markup=_markup())
        finally:
            raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:(restart|partner)$"), group=-30000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, night_login), group=-29999)
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: message_gate(u, c, B)), group=-29998)
    app.add_handler(CallbackQueryHandler(callback_gate), group=-29997)
    B._offhours_partner_gate_v5 = True
    return True


async def message_gate(update, context, B):
    if is_open():
        return
    user = getattr(update, "effective_user", None)
    msg = getattr(update, "effective_message", None)
    if not user or not msg:
        return
    if _allowed_during_closed(B, user.id):
        return
    await msg.reply_text(_closed_text(), reply_markup=_markup())
    raise ApplicationHandlerStop
