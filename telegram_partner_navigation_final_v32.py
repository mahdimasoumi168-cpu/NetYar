"""Final partner navigation hardening.

Goals:
- Every explicit entry into the partner panel starts a fresh login.
- Partner-service Cancel returns to the partner panel instead of the public menu.
- Partner authentication is preserved while navigating inside the panel.
- Existing partner services and the existing admin 'add partner' capability are
  left intact; this module only owns the two navigation edge cases.
"""
import logging

from telegram.ext import ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_navigation_v32")

PARTNER_LABELS = {
    "👥 پنل همکاران",
    "🔵 👥 پنل همکاران",
    "👥 Partner panel",
    "👥 لوحة الشركاء",
}
CANCEL_LABELS = {
    "❌ انصراف",
    "❌ Cancel",
    "❌ إلغاء",
    "انصراف",
    "Cancel",
    "إلغاء",
}


def _fresh_partner_login(B, uid):
    old = dict(B.S.get(uid, {}) or {})
    keep = {}
    for key in ("lang", "status", "citizenship"):
        if old.get(key) is not None:
            keep[key] = old[key]
    keep.update({
        "partner_logged_out": True,
        "partner_active": False,
        "mode": "p_phone",
        "step": "partner_phone",
    })
    B.S[uid] = keep
    return keep


def _clear_partner_flow_keep_auth(B, uid):
    st = B.S.setdefault(uid, {})
    # Preserve authenticated partner identity, but remove every service/input
    # continuation so the next action starts from the partner menu.
    preserved = {
        key: st.get(key)
        for key in (
            "lang", "status", "citizenship", "partner", "partner_phone",
            "partner_id", "partner_active", "partner_logged_out",
        )
        if st.get(key) is not None
    }
    preserved["mode"] = "partner"
    preserved["step"] = "partner"
    B.S[uid] = preserved
    return B.S[uid]


def install(app, B):
    if getattr(B, "_partner_navigation_v32", False):
        return True

    import telegram_ui_policy_v2 as UI
    original_dispatch = UI._dispatch

    async def dispatch(update, context, bot, label):
        label = str(label or "").strip()
        q = getattr(update, "callback_query", None)
        uid = int(q.from_user.id if q else update.effective_user.id)
        st = bot.S.setdefault(uid, {})

        if label in PARTNER_LABELS:
            # Never reopen an already-authenticated partner session silently.
            # A deliberate press of the panel button is always a new login.
            st = _fresh_partner_login(bot, uid)
            if q:
                await q.answer()
                await q.message.reply_text(
                    "👥 ورود به پنل همکاران\n\n"
                    "📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
                    reply_markup=bot.cancel_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop
            return await update.effective_message.reply_text(
                "👥 ورود به پنل همکاران\n\n"
                "📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
                reply_markup=bot.cancel_kb(st.get("lang", "fa")),
            )

        if label in CANCEL_LABELS and st.get("partner_active") and not st.get("partner_logged_out"):
            # Cancel inside a partner service means 'back to partner panel',
            # not 'back to public main menu'.
            _clear_partner_flow_keep_auth(bot, uid)
            if q:
                await q.answer()
                await q.message.reply_text(
                    "↩️ به پنل همکاران برگشتید.",
                    reply_markup=bot.partner_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop
            return await update.effective_message.reply_text(
                "↩️ به پنل همکاران برگشتید.",
                reply_markup=bot.partner_kb(st.get("lang", "fa")),
            )

        return await original_dispatch(update, context, bot, label)

    UI._dispatch = dispatch
    B._partner_navigation_v32 = True
    log.info("Partner navigation v32 installed")
    return True
