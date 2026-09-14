"""Highest-priority cancel handler for the v3 government flow."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_gov_cancel_fix", False):
        return

    async def cancel(update, context):
        q = update.callback_query
        if not q or q.data != "govv3:cancel":
            return
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        partner_id = st.get("partner_id")
        lang = st.get("lang", "fa")
        st.clear()
        st.update({"status": "foreign", "lang": lang})
        if partner_id:
            st["partner_id"] = partner_id
            st["partner_active"] = True
            markup = B.partner_kb(lang)
        else:
            markup = B.main(uid)
        await q.message.reply_text("❌ عملیات لغو شد.", reply_markup=markup)
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cancel, pattern=r"^govv3:cancel$"), group=-130)
    B._gov_cancel_fix = True
