"""Deterministic Telegram partner-panel callback guard.

The production bot has several legacy layers that can overwrite partner
handlers and keyboards. Partner entry must therefore be isolated from those
mutable wrappers. This guard also provides its own cancel keyboard so the
entry path cannot fail because another patch replaced B.cancel_kb.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_router_guard")
PARTNER = "👥 پنل همکاران"
CANCEL = "❌ انصراف"


def _cancel_markup(B, UI, uid):
    return UI.inline([[CANCEL]], B, uid)


def _partner_markup(B, UI, uid):
    return UI.inline(
        [
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            [CANCEL],
        ],
        B,
        uid,
    )


async def _open_partner_from_callback(update, context, B, UI):
    q = update.callback_query
    uid = int(q.from_user.id)
    st = B.S.setdefault(uid, {})

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

    st["mode"] = "p_phone"
    st.pop("phone", None)
    st.pop("partner_active", None)
    return await q.message.reply_text(
        "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
        reply_markup=_cancel_markup(B, UI, uid),
    )


def install():
    import bot as B
    import telegram_ui_policy_v2 as UI

    if getattr(UI, "_partner_router_guard_v3", False):
        return

    original_dispatch = UI._dispatch

    async def guarded_dispatch(update, context, bot_obj, label):
        if str(label or "").strip() == PARTNER:
            return await _open_partner_from_callback(update, context, bot_obj, UI)
        return await original_dispatch(update, context, bot_obj, label)

    UI._dispatch = guarded_dispatch
    UI._partner_router_guard_v3 = True

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

    B.partner_kb = safe_partner_kb
    B.cancel_kb = safe_cancel_kb
    try:
        import telegram_business_features as F
        F._partner_kb = lambda: safe_partner_kb()
    except Exception:
        log.exception("could not lock legacy partner keyboard")

    log.info("Telegram partner router guard v3 installed")
