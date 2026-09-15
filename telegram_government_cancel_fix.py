"""Highest-priority cancel handler for the v3 government flow.

Cancelling a service must cancel only the current service flow. If the user
entered the service from the partner panel, the partner session is preserved
and the partner panel is shown again instead of logging the partner out.
"""
from telegram import CallbackQueryHandler
from telegram.ext import ApplicationHandlerStop


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

        # Capture the partner session BEFORE clearing the temporary service
        # state. Never destroy an authenticated partner session just because
        # the partner cancelled one service.
        partner_id = st.get("partner_id")
        partner_active = bool(st.get("partner_active", False))
        partner_phone = st.get("partner_phone")
        partner_username = st.get("partner_username")
        lang = st.get("lang", "fa")

        st.clear()
        st.update({"status": "foreign", "lang": lang})

        if partner_id and partner_active:
            st.update({
                "partner_id": partner_id,
                "partner_active": True,
            })
            if partner_phone:
                st["partner_phone"] = partner_phone
            if partner_username:
                st["partner_username"] = partner_username
            markup = B.partner_kb(lang)
            message = "❌ عملیات لغو شد.\n\n👥 به پنل همکاران بازگشتید."
        else:
            markup = B.main(uid)
            message = "❌ عملیات لغو شد.\n\n🏠 به منوی اصلی بازگشتید."

        await q.message.reply_text(message, reply_markup=markup)
        raise ApplicationHandlerStop

    # Highest priority: this must win over legacy government cancel handlers.
    app.add_handler(CallbackQueryHandler(cancel, pattern=r"^govv3:cancel$"), group=-130)
    B._gov_cancel_fix = True
