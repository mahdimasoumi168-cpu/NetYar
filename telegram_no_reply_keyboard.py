"""Remove legacy Telegram ReplyKeyboard UI.

All navigation is now message-attached inline buttons. This module also sends
ReplyKeyboardRemove after /start so users who already received the old keyboard
lose it immediately.
"""
from telegram import ReplyKeyboardRemove


_INVISIBLE = "\u200b"


def install(app, B):
    if getattr(B, "_netyar_no_reply_keyboard", False):
        return

    old_start = B.start

    async def start_without_reply_keyboard(update, context):
        result = await old_start(update, context)
        try:
            if update.message:
                await update.message.reply_text(
                    _INVISIBLE,
                    reply_markup=ReplyKeyboardRemove(),
                )
        except Exception:
            pass
        return result

    B.start = start_without_reply_keyboard
    B._netyar_no_reply_keyboard = True
