"""Deterministic Telegram entry routing for partner/admin panels.

This guard is intentionally small: it only owns the two panel-entry labels.
All other callbacks remain with the canonical Telegram router.
"""
import logging

log = logging.getLogger("netyar.telegram.entry_router_guard")
PARTNER = "👥 پنل همکاران"
ADMIN_PANEL = "🛠 پنل مدیریت بات"
CANCEL = "❌ انصراف"


def _is_admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        log.exception("admin authorization check failed")
        return False


def _partner_markup(B, UI, uid):
    rows = [
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        ["🔎 پیگیری کد", "📋 سوابق"],
        ["💰 موجودی", "🎫 تیکت به مدیریت"],
    ]
    if _is_admin(B, uid):
        rows.append([ADMIN_PANEL])
    rows.extend([["🚪 خروج از پنل"], [CANCEL]])
    try:
        return UI.inline(rows, B, uid)
    except Exception:
        log.exception("partner markup failed")
        return None


async def _login(message, B, UI, uid, st):
    st["mode"] = "p_phone"
    st.pop("phone", None)
    st.pop("partner_active", None)
    markup = None
    try:
        markup = UI.inline([[CANCEL]], B, uid)
    except Exception:
        pass
    kwargs = {"reply_markup": markup} if markup is not None else {}
    return await message.reply_text(
        "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
        **kwargs,
    )


async def _open_partner(update, context, B, UI):
    q = update.callback_query
    if not q or not q.message:
        return
    uid = int(q.from_user.id)
    st = B.S.setdefault(uid, {})
    try:
        if st.get("partner_logged_out"):
            st.pop("partner_id", None)
            st.pop("partner_active", None)
        pid = st.get("partner_id")
        if pid and st.get("partner_active", True):
            row = B.db.conn.execute(
                "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)
            ).fetchone()
            if row:
                st["partner_active"] = True
                st["partner_logged_out"] = False
                st["mode"] = None
                try:
                    name = row["name"] or "-"
                    phone = row["phone"] or "-"
                    balance = int(row["balance"] or 0)
                except Exception:
                    name, phone, balance = "-", "-", 0
                markup = _partner_markup(B, UI, uid)
                kwargs = {"reply_markup": markup} if markup is not None else {}
                return await q.message.reply_text(
                    f"👥 پنل همکاران\n👤 {name}\n📱 {phone}\n💰 اعتبار: {balance:,} تومان",
                    **kwargs,
                )
        return await _login(q.message, B, UI, uid, st)
    except Exception:
        log.exception("partner entry failed")
        st["mode"] = "p_phone"
        return await q.message.reply_text(
            "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:"
        )


async def _open_admin(update, context, B):
    q = update.callback_query
    if not q or not q.message:
        return
    uid = int(q.from_user.id)
    if not _is_admin(B, uid):
        return await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
    try:
        import telegram_admin_plus as A
        return await q.message.reply_text(
            "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
            reply_markup=A._admin_menu(),
        )
    except Exception:
        log.exception("admin entry failed")
        return await q.message.reply_text("🛠 پنل مدیریت در حال آماده‌سازی است. لطفاً دوباره تلاش کنید.")


def install():
    import bot as B
    import telegram_ui_policy_v2 as UI

    original = getattr(UI, "_entry_router_original_dispatch", None)
    if original is None:
        original = UI._dispatch
        UI._entry_router_original_dispatch = original

    async def dispatch(update, context, bot_obj, label):
        label = str(label or "").strip()
        if label == PARTNER:
            return await _open_partner(update, context, bot_obj, UI)
        if label == ADMIN_PANEL:
            return await _open_admin(update, context, bot_obj)
        return await original(update, context, bot_obj, label)

    UI._dispatch = dispatch

    def partner_kb(lang="fa"):
        uid = UI._uid() or getattr(B, "_ui_current_uid", None) or 0
        return _partner_markup(B, UI, uid)

    B.partner_kb = partner_kb
    B.cancel_kb = lambda lang="fa": UI.inline([[CANCEL]], B, UI._uid() or 0)
    B.partner = lambda update, context: _open_partner_from_message(update, context, B, UI)

    log.info("Telegram entry router guard installed")


async def _open_partner_from_message(update, context, B, UI):
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    uid = int(update.effective_user.id)
    st = B.S.setdefault(uid, {})
    try:
        if st.get("partner_logged_out"):
            st.pop("partner_id", None)
            st.pop("partner_active", None)
        pid = st.get("partner_id")
        if pid and st.get("partner_active", True):
            row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            if row:
                st["partner_active"] = True
                st["mode"] = None
                markup = _partner_markup(B, UI, uid)
                kwargs = {"reply_markup": markup} if markup is not None else {}
                return await message.reply_text(
                    f"👥 پنل همکاران\n👤 {row['name'] or '-'}\n📱 {row['phone'] or '-'}\n💰 اعتبار: {int(row['balance'] or 0):,} تومان",
                    **kwargs,
                )
        return await _login(message, B, UI, uid, st)
    except Exception:
        log.exception("partner message entry failed")
        st["mode"] = "p_phone"
        return await message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:")
