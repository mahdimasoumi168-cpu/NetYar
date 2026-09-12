"""High-priority guard for the residence-booklet Telegram flow."""
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop


def install(app, B):
    import telegram_residence_booklet as R

    async def _media(update, context):
        st = B.S.setdefault(update.effective_user.id, {})
        if st.get("gov_doc_type") != "residence_booklet":
            return
        if st.get("mode") != "gov_photo":
            return
        await R._residence_media(update, context, B)
        raise ApplicationHandlerStop

    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, _media),
        group=-7,
    )
