"""Preflight balance guard for the v3 Government service.

Runs before the v3 final-submit callback. It never changes a valid flow; it only
blocks a partner when the active balance cannot cover the configured service price.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_gov_v3_balance_guard", False):
        return

    async def guard(update, context):
        q = update.callback_query
        if not q or q.data != "govv3:sim_no":
            return
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        if not pid:
            return
        amount = int(B.db.setting("price_government", "500000") or 500000)
        row = B.db.conn.execute(
            "SELECT balance, active FROM partners WHERE id=?", (pid,)
        ).fetchone()
        balance = int(row["balance"] or 0) if row else 0
        active = bool(row and row["active"])
        if not active or balance < amount:
            await q.answer("اعتبار کافی نیست", show_alert=True)
            await q.message.reply_text(
                f"❌ اعتبار پنل همکاران کافی نیست.\n\n"
                f"💳 اعتبار فعلی: {balance:,} تومان\n"
                f"💰 هزینه خدمت: {amount:,} تومان\n\n"
                "ابتدا حساب را از طریق «➕ شارژ حساب» شارژ و تأیید مدیریت کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ شارژ حساب", callback_data="partner:topup")],
                    [InlineKeyboardButton("❌ انصراف", callback_data="govv3:cancel")],
                ]),
            )
            raise ApplicationHandlerStop
        return

    app.add_handler(CallbackQueryHandler(guard, pattern=r"^govv3:sim_no$"), group=-130)
    B._gov_v3_balance_guard = True
