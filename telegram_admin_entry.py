"""Admin entry routing for the inline main-menu button."""
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop


async def _cb(update, context, B):
    q = update.callback_query
    if not q or not q.data.startswith("ui:"):
        return
    label = q.data[3:]
    if "پنل مدیریت بات" not in label or not B.admin(q.from_user.id):
        return
    await q.answer()
    await q.message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=B.amenu())
    raise ApplicationHandlerStop


def install(app, B):
    app.add_handler(CallbackQueryHandler(lambda u,c:_cb(u,c,B), pattern=r"^ui:"), group=-6)
