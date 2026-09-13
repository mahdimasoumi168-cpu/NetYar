"""Deterministic Telegram partner-panel entry owner.

This module is installed LAST so the partner entry and partner keyboard cannot
fall back to legacy handlers that produce the generic UI execution error.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_router_guard")
PARTNER = "👥 پنل همکاران"
ADMIN_PANEL = "🛠 پنل مدیریت بات"
CANCEL = "❌ انصراف"


def _cancel_markup(B, UI, uid):
    try:
        return UI.inline([[CANCEL]], B, uid)
    except Exception:
        log.exception("partner cancel markup failed")
        return None


def _is_admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        log.exception("admin authorization check failed uid=%s", uid)
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


async def _login_prompt_message(message, B, UI, uid, st):
    st["mode"] = "p_phone"
    st.pop("phone", None)
    st.pop("partner_active", None)
    markup = _cancel_markup(B, UI, uid)
    kwargs = {"reply_markup": markup} if markup is not None else {}
    return await message.reply_text(
        "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
        **kwargs,
    )


async def _open_partner_from_callback(update, context, B, UI):
    q = update.callback_query
    if q is None or q.message is None:
        return None
    uid = int(q.from_user.id)
    st = B.S.setdefault(uid, {})

    try:
        if st.get("partner_logged_out"):
            st.pop("partner_id", None)
            st.pop("partner_active", None)

        pid = st.get("partner_id")
        if pid and st.get("partner_active", True):
            try:
                p = B.db.conn.execute(
                    "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)
                ).fetchone()
            except Exception:
                log.exception("partner lookup failed")
                p = None

            if p:
                st["partner_active"] = True
                st["partner_logged_out"] = False
                st["mode"] = None
                try:
                    name = p["name"] or "-"
                    phone = p["phone"] or "-"
                    balance = int(p["balance"] or 0)
                except Exception:
                    name = phone = "-"
                    balance = 0
                markup = _partner_markup(B, UI, uid)
                kwargs = {"reply_markup": markup} if markup is not None else {}
                return await q.message.reply_text(
                    f"👥 پنل همکاران\n👤 {name}\n📱 {phone}\n💰 اعتبار: {balance:,} تومان",
                    **kwargs,
                )

        return await _login_prompt_message(q.message, B, UI, uid, st)
    except Exception:
        log.exception("partner callback guard failed; forcing login flow")
        # Never allow this entry point to bubble an exception into ui2's generic
        # error message. Even if the database is unavailable, show the login form.
        try:
            return await _login_prompt_message(q.message, B, UI, uid, st)
        except Exception:
            log.exception("partner callback fallback failed")
            return await q.message.reply_text(
                "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:"
            )


async def _open_partner_from_message(update, context, B, UI):
    uid = int(update.effective_user.id)
    st = B.S.setdefault(uid, {})
    message = update.effective_message or update.message
    if message is None:
        return None
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
                    name = phone = "-"
                    balance = 0
                markup = _partner_markup(B, UI, uid)
                kwargs = {"reply_markup": markup} if markup is not None else {}
                return await message.reply_text(
                    f"👥 پنل همکاران\n👤 {name}\n📱 {phone}\n💰 اعتبار: {balance:,} تومان",
                    **kwargs,
                )
        return await _login_prompt_message(message, B, UI, uid, st)
    except Exception:
        log.exception("partner message entry failed; forcing login prompt")
        try:
            return await _login_prompt_message(message, B, UI, uid, st)
        except Exception:
            return await message.reply_text(
                "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:"
            )


def install():
    import bot as B
    import telegram_ui_policy_v2 as UI

    # Do not use a stale one-time marker here. Runtime layers may import this
    # module before the final UI dispatcher is fully installed. Re-wrapping is
    # intentionally idempotent through our own marker and always points at the
    # current dispatcher.
    original_dispatch = getattr(UI, "_partner_guard_original_dispatch", None)
    if original_dispatch is None:
        original_dispatch = UI._dispatch
        UI._partner_guard_original_dispatch = original_dispatch

    async def guarded_dispatch(update, context, bot_obj, label):
        normalized = str(label or "").strip()
        if normalized == PARTNER:
            return await _open_partner_from_callback(update, context, bot_obj, UI)
        return await original_dispatch(update, context, bot_obj, label)

    UI._dispatch = guarded_dispatch
    UI._partner_router_guard_v6 = True

    def safe_partner_kb(lang="fa"):
        uid = UI._uid()
        if uid is None:
            uid = getattr(B, "_ui_current_uid", None) or 0
        return _partner_markup(B, UI, uid)

    def safe_cancel_kb(lang="fa"):
        uid = UI._uid()
        if uid is None:
            uid = getattr(B, "_ui_current_uid", None) or 0
        return _cancel_markup(B, UI, uid)

    B.partner = lambda update, context: _open_partner_from_message(update, context, B, UI)
    B.partner_kb = safe_partner_kb
    B.cancel_kb = safe_cancel_kb

    try:
        import telegram_business_features as F
        F._partner_kb = lambda: safe_partner_kb()
    except Exception:
        log.exception("could not lock legacy partner keyboard")

    log.info("Telegram partner router guard v7 installed")
