"""Deterministic Telegram partner-panel callback guard.

The production bot has several legacy layers that can overwrite B.partner_kb
or wrap B.partner.  The partner-panel entry callback must not depend on any
of those mutable wrappers.  This module therefore owns only the inline
partner-panel entry path and delegates every other label to the canonical UI
router.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_router_guard")

PARTNER = "👥 پنل همکاران"


def _partner_markup(B, UI, uid):
    return UI.inline(
        [
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ],
        B,
        uid,
    )


async def _open_partner_from_callback(update, context, B, UI):
    q = update.callback_query
    uid = int(q.from_user.id)
    st = B.S.setdefault(uid, {})

    # A deliberate logout always wins over automatic Telegram linking.
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
            return await q.message.reply_text(
                f"👥 پنل همکاران\n👤 {name}\n📱 {phone}\n💰 اعتبار: {balance:,} تومان",
                reply_markup=_partner_markup(B, UI, uid),
            )

    # No active partner session: start the normal partner login flow.
    st["mode"] = "p_phone"
    st.pop("phone", None)
    st.pop("partner_active", None)
    return await q.message.reply_text(
        "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
        reply_markup=B.cancel_kb(st.get("lang", "fa")),
    )


def install():
    import bot as B
    import telegram_ui_policy_v2 as UI

    if getattr(UI, "_partner_router_guard_v2", False):
        return

    original_dispatch = UI._dispatch

    async def guarded_dispatch(update, context, bot_obj, label):
        if str(label or "").strip() == PARTNER:
            return await _open_partner_from_callback(update, context, bot_obj, UI)
        return await original_dispatch(update, context, bot_obj, label)

    UI._dispatch = guarded_dispatch
    UI._partner_router_guard_v2 = True

    # Keep the keyboard safe for all older text-based partner flows as well.
    def safe_partner_kb(lang="fa"):
        uid = UI._uid()
        if uid is None:
            uid = getattr(B, "_ui_current_uid", None) or 0
        return _partner_markup(B, UI, uid)

    B.partner_kb = safe_partner_kb
    try:
        import telegram_business_features as F
        F._partner_kb = lambda: safe_partner_kb()
    except Exception:
        log.exception("could not lock legacy partner keyboard")

    log.info("Telegram partner router guard v2 installed")
