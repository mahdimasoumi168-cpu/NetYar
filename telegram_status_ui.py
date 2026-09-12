"""Canonical Telegram language/citizenship menu handlers."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler


def install(app, B):
    if getattr(B, "_canonical_status_ui", False):
        return

    async def status(update, context):
        q = update.callback_query
        if not q:
            return
        await q.answer()
        uid = q.from_user.id
        value = str(q.data or "").split(":", 1)[-1]
        st = B.S.setdefault(uid, {})
        st["status"] = value
        st["mode"] = None
        if value == "iranian":
            text = "🇮🇷 منوی خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:"
        else:
            text = "منوی خدمات کمک یار مهاجر 👇"
        return await q.message.reply_text(text, reply_markup=B.main(uid))

    B.statuscb = status
    app.add_handler(CallbackQueryHandler(status, pattern=r"^st:(foreign|iranian)$"), group=-100)
    B._canonical_status_ui = True
