"""Reliable Telegram partner-panel UI.

Authorized partners get the partner menu only while their session is active.
An explicit logout blocks automatic relinking until the user starts a new
partner-panel login flow.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_ui")


def _partner_row(B, uid):
    st = B.S.setdefault(uid, {})
    # Explicit logout is authoritative. Do not silently re-link the Telegram
    # account from partner_telegram_links until the user starts login again.
    if st.get("partner_logged_out"):
        return None
    pid = st.get("partner_id")
    try:
        if pid:
            row = B.db.conn.execute(
                "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)
            ).fetchone()
            if row:
                st["partner_active"] = True
                return row
        row = B.db.conn.execute(
            "SELECT p.* FROM partners p "
            "JOIN partner_telegram_links l ON l.partner_id=p.id "
            "WHERE l.telegram_user_id=? AND p.active=1 LIMIT 1",
            (str(uid),),
        ).fetchone()
        if row:
            st["partner_id"] = row["id"]
            st["partner_active"] = True
            return row
    except Exception:
        log.exception("partner lookup failed")
    return None


def install(app, B):
    if getattr(B, "_partner_ui_fix", False):
        return
    import telegram_business_features as F
    import telegram_ui_policy_v2 as UI

    def partner_inline(uid=None):
        return UI.inline([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)

    F._partner_kb = lambda: partner_inline()
    B.partner_kb = lambda lang="fa": partner_inline()

    old_partner = B.partner

    async def partner(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        row = _partner_row(B, uid)
        if row:
            st["partner_id"] = row["id"]
            st["partner_active"] = True
            st["partner_logged_out"] = False
            st["mode"] = None
            await update.message.reply_text(
                f"👥 پنل همکاران\n"
                f"👤 {row['name']}\n"
                f"📱 {row['phone']}\n"
                f"💰 اعتبار: {int(row['balance'] or 0):,} تومان",
                reply_markup=partner_inline(uid),
            )
            return
        # No active session (including after explicit logout): enter the normal
        # login/registration flow instead of auto-entering the panel.
        return await old_partner(update, context)

    B.partner = partner
    B._partner_ui_fix = True
