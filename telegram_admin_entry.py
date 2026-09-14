"""Telegram admin entry routing for keyboard and inline buttons.

This is the canonical entry point for the administrator panel.  It accepts the
current Persian label plus the visual-prefix variants produced by UI layers.
"""
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

ADMIN_LABELS = {
    "🛠 پنل مدیریت بات",
    "🛠 پنل مدیریت",
    "پنل مدیریت بات",
    "پنل مدیریت",
    "🔵 🛠 پنل مدیریت بات",
    "🔷 🛠 پنل مدیریت بات",
    "🟦 🛠 پنل مدیریت بات",
    "🟢 🛠 پنل مدیریت بات",
}


def _clean(text):
    t=(text or "").strip()
    prefixes=("🔵 ","🔷 ","🟦 ","🟢 ","🟠 ","🟣 ","🟡 ","⚪ ")
    changed=True
    while changed:
        changed=False
        for p in prefixes:
            if t.startswith(p):
                t=t[len(p):].strip()
                changed=True
                break
    return t


async def _show_admin(update, B):
    user = update.effective_user
    if not user or not B.admin(user.id):
        return False
    message = update.effective_message
    if not message:
        return False
    import telegram_admin_plus as A
    # Always use the latest patched menu, including the full admin-power layer.
    menu = A._admin_menu()
    await message.reply_text(
        "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
        reply_markup=menu,
    )
    return True


async def _cb(update, context, B):
    q = update.callback_query
    if not q or not q.data.startswith("ui:"):
        return
    label = _clean(q.data[3:])
    if label not in {_clean(x) for x in ADMIN_LABELS} or not B.admin(q.from_user.id):
        return
    await q.answer()
    if await _show_admin(update, B):
        raise ApplicationHandlerStop


async def _text(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not B.admin(user.id):
        return
    text = _clean(message.text)
    if text not in {_clean(x) for x in ADMIN_LABELS}:
        return
    if await _show_admin(update, B):
        raise ApplicationHandlerStop


def install(app, B):
    # Inline entry used by newer UI layers.
    app.add_handler(
        CallbackQueryHandler(lambda u, c: _cb(u, c, B), pattern=r"^ui:"),
        group=-20,
    )
    # The actual main-menu button is a ReplyKeyboard button.  Handle every
    # known visual variant before generic routers can consume it.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)),
        group=-20,
    )
