"""Fast Telegram response layer.

Owns the earliest Telegram /start path so legacy startup wrappers cannot
replace the canonical welcome message or send a second startup message.
"""
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationHandlerStop
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

WELCOME = (
    "👋 سلام!\n"
    "به سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n"
    "اینجا تلاش کرده‌ایم خدمات موردنیاز شما را به‌صورت سریع، ساده و آنلاین در اختیارتان قرار دهیم تا بدون سردرگمی بتوانید خدمت موردنظر خود را دریافت یا پیگیری کنید.\n"
    "🚀 بات، کمک یار مهاجر؛ خدماتی برای شما، درآمدی برای همه\n"
    "📌 لطفاً ابتدا زبان موردنظر خود را انتخاب کنید تا ادامه مراحل به زبان انتخابی شما نمایش داده شود.\n"
    "🇮🇷 فارسی\n"
    "🇬🇧 English\n"
    "🇸🇦 العربية"
)


def install(app, B):
    if getattr(B, "_fast_response_layer", False):
        return

    async def fast_start(update, context):
        user = getattr(update, "effective_user", None)
        msg = getattr(update, "message", None)
        if not user or not msg:
            return
        uid = user.id
        B.S[uid] = {}
        try:
            B.db.user("telegram", uid, user.username, user.full_name)
        except Exception:
            pass
        await msg.reply_text(
            WELCOME,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
                InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar"),
            ]])
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
