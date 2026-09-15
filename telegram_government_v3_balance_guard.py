"""Preflight balance guard for the v3 Government service.

Runs before both final-submit paths. It never changes a valid flow; it only blocks
a partner when the active balance cannot cover the configured service price.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters


def install(app, B):
    if getattr(B, "_gov_v3_balance_guard", False):
        return

    async def _check(update):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        if not pid:
            return True
        amount = int(B.db.setting("price_government", "500000") or 500000)
        row = B.db.conn.execute("SELECT balance, active FROM partners WHERE id=?", (pid,)).fetchone()
        balance = int(row["balance"] or 0) if row else 0
        active = bool(row and row["active"])
        if active and balance >= amount:
            return True
        target = update.callback_query.message if update.callback_query else update.effective_message
        if update.callback_query:
            await update.callback_query.answer("اعتبار کافی نیست", show_alert=True)
        await target.reply_text(
            f"❌ اعتبار پنل همکاران کافی نیست.\n\n"
            f"💳 اعتبار فعلی: {balance:,} تومان\n"
            f"💰 هزینه خدمت: {amount:,} تومان\n\n"
            "ابتدا حساب را از طریق «➕ شارژ حساب» شارژ و تأیید مدیریت کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ شارژ حساب", callback_data="partner:topup")],
                [InlineKeyboardButton("❌ انصراف", callback_data="govv3:cancel")],
            ]),
        )
        return False

    async def callback_guard(update, context):
        q = update.callback_query
        if not q or q.data != "govv3:sim_no":
            return
        if not await _check(update):
            raise ApplicationHandlerStop

    async def media_guard(update, context):
        msg = update.effective_message
        if not msg:
            return
        st = B.S.setdefault(update.effective_user.id, {})
        if st.get("mode") != "govv3_sim_optional":
            return
        if not await _check(update):
            raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback_guard, pattern=r"^govv3:sim_no$"), group=-130)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, media_guard), group=-130)
    B._gov_v3_balance_guard = True
