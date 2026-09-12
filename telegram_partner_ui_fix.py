"""Reliable Telegram partner-panel UI.

Authorized partners always get a fresh inline partner menu. The persistent
ReplyKeyboard remains reserved for the global restart action.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_ui")


def _partner_row(B, uid):
    st = B.S.setdefault(uid, {})
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
        row = _partner_row(B, uid)
        if row:
            st = B.S.setdefault(uid, {})
            st["partner_id"] = row["id"]
            st["partner_active"] = True
            st["mode"] = None
            await update.message.reply_text(
                f"👥 پنل همکاران\n"
                f"👤 {row['name']}\n"
                f"📱 {row['phone']}\n"
                f"💰 اعتبار: {int(row['balance'] or 0):,} تومان",
                reply_markup=partner_inline(uid),
            )
            return
        return await old_partner(update, context)

    B.partner = partner
    B._partner_ui_fix = True
