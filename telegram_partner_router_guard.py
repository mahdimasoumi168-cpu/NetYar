"""Deterministic Telegram partner-panel entry owner.

This module is installed LAST because the production bot contains legacy layers
that can replace B.partner, B.partner_kb, and B.cancel_kb. Both inline-callback
entry and legacy reply/inline keyboards therefore converge on one safe handler.
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
    # Admin access is deliberately decided at render time so a normal partner
    # never receives a management button and an admin does not lose it after
    # entering the partner panel.
    if _is_admin(B, uid):
        rows.append([ADMIN_PANEL])
    rows.extend([
        ["🚪 خروج از پنل"],
        [CANCEL],
    ])
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
                    "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1",
                    (pid,),
                ).fetchone()
            except Exception:
                log.exception("partner lookup failed")
                p = None

            if p:
                st["partner_active"] = True
                st["mode"] = None
                st["partner_logged_out"] = False
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
        try:
            return await _login_prompt_message(q.message, B, UI, uid, st)
        except Exception:
            log.exception("partner callback fallback failed")
            return await q.message.reply_text(
                "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:"
            )


async def _open_partner_from_message(update, context, B, UI):
    """Hard-lock B.partner so legacy reply keyboards cannot call a broken wrapper."""
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

    if getattr(UI, "_partner_router_guard_v5", False):
        return

    original_dispatch = UI._dispatch

    async def guarded_dispatch(update, context, bot_obj, label):
        # Admin panel is already implemented by the canonical UI dispatcher.
        # Keep that route intact; only the partner-entry label is hard-locked here.
        if str(label or "").strip() == PARTNER:
            return await _open_partner_from_callback(update, context, bot_obj, UI)
        return await original_dispatch(update, context, bot_obj, label)

    UI._dispatch = guarded_dispatch
    UI._partner_router_guard_v5 = True

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

    # These assignments are intentionally last: they prevent older layers from
    # replacing the partner entry or partner keyboard after this guard is installed.
    B.partner = lambda update, context: _open_partner_from_message(update, context, B, UI)
    B.partner_kb = safe_partner_kb
    B.cancel_kb = safe_cancel_kb

    try:
        import telegram_business_features as F
        F._partner_kb = lambda: safe_partner_kb()
    except Exception:
        log.exception("could not lock legacy partner keyboard")

    log.info("Telegram partner router guard v6 installed")
