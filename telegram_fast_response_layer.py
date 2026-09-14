"""Fast Telegram response layer.

Acknowledges callback buttons immediately so Telegram stops showing a spinner while
business handlers continue, and handles /start before the large legacy router stack.
"""
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationHandlerStop
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def install(app, B):
    if getattr(B, "_fast_response_layer", False):
        return

    async def fast_start(update, context):
        user = getattr(update, "effective_user", None)
        msg = getattr(update, "message", None)
        if not user or not msg:
            return
        uid = user.id
        old = B.S.get(uid, {})
        B.S[uid] = {k: old[k] for k in ("partner_id", "partner_active", "admin", "lang", "status", "phone") if k in old}
        try:
            B.db.user("telegram", uid, user.username, user.full_name)
        except Exception:
            pass
        await msg.reply_text(
            "👋 سلام!\n\nبه سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\nلطفاً زبان را انتخاب کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"), InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"), InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar")]])
        )
        raise ApplicationHandlerStop

    async def fast_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        try:
            await q.answer()
        except Exception:
            pass

    app.add_handler(CommandHandler(["start", "srart"], fast_start), group=-2000001)
    app.add_handler(CallbackQueryHandler(fast_callback), group=-2000002)
    B._fast_response_layer = True
