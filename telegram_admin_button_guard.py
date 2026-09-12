"""Terminal Telegram guard for the admin-panel reply-keyboard button."""
from telegram.ext import ApplicationHandlerStop, MessageHandler, filters

LABELS = {
    "🛠 پنل مدیریت بات",
    "🛠 پنل مدیریت",
    "🔵 🛠 پنل مدیریت بات",
    "🔵 🛠 پنل مدیریت",
    "پنل مدیریت بات",
    "پنل مدیریت",
}


async def _handle(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not B.admin(user.id):
        return
    if str(message.text or "").strip() not in LABELS:
        return
    st = B.S.setdefault(user.id, {})
    st["admin"] = True
    st["mode"] = None
    st["admin_mode"] = None
    await message.reply_text(
        "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
        reply_markup=B.amenu(),
    )
    raise ApplicationHandlerStop


def install(app, B):
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _handle(u, c, B)),
        group=-200,
    )
