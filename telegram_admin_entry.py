"""Telegram admin entry routing for keyboard and inline buttons."""
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

ADMIN_LABELS = {
    "🛠 پنل مدیریت بات",
    "🛠 پنل مدیریت",
    "پنل مدیریت بات",
    "پنل مدیریت",
}


async def _show_admin(update, B):
    user = update.effective_user
    if not user or not B.admin(user.id):
        return False
    message = update.effective_message
    if not message:
        return False
    await message.reply_text(
        "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
        reply_markup=B.amenu(),
    )
    return True


async def _cb(update, context, B):
    q = update.callback_query
    if not q or not q.data.startswith("ui:"):
        return
    label = q.data[3:]
    if not any(x in label for x in ADMIN_LABELS) or not B.admin(q.from_user.id):
        return
    await q.answer()
    await _show_admin(update, B)
    raise ApplicationHandlerStop


async def _text(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not B.admin(user.id):
        return
    text = (message.text or "").strip()
    if text not in ADMIN_LABELS:
        return
    await _show_admin(update, B)
    raise ApplicationHandlerStop


def install(app, B):
    # Inline entry used by newer UI layers.
    app.add_handler(
        CallbackQueryHandler(lambda u, c: _cb(u, c, B), pattern=r"^ui:"),
        group=-20,
    )
    # The actual main menu button is a ReplyKeyboard button. It previously had
    # no direct handler, so it fell through to legacy routers and appeared dead.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)),
        group=-20,
    )
