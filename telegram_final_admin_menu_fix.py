"""Final Telegram admin-menu reliability layer.

Provides a deterministic admin keyboard independent of legacy menu wrappers.
It also makes the admin reply-keyboard entry deterministic for authorized admins.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

ADMIN_LABELS = {"🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت"}


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 کاربران", callback_data="adm:users"), InlineKeyboardButton("👥 همکاران", callback_data="adm:partners")],
        [InlineKeyboardButton("➕ افزودن همکار جدید", callback_data="adm:addpartner")],
        [InlineKeyboardButton("💰 شارژها", callback_data="adm:topups"), InlineKeyboardButton("💳 پرداخت‌ها", callback_data="adm:payments")],
        [InlineKeyboardButton("📋 درخواست‌ها", callback_data="adm:requests"), InlineKeyboardButton("⚙️ قیمت‌ها", callback_data="adm:prices")],
        [InlineKeyboardButton("➕ افزایش قیمت", callback_data="adm:priceup"), InlineKeyboardButton("➖ کاهش قیمت", callback_data="adm:pricedown")],
        [InlineKeyboardButton("💵 افزایش شارژ", callback_data="adm:creditup"), InlineKeyboardButton("💸 کاهش شارژ", callback_data="adm:creditdown")],
        [InlineKeyboardButton("📈 قیمت‌گذاری تک‌تک خدمات همکار", callback_data="ppx:start")],
        [InlineKeyboardButton("✏️ تغییر متن‌ها", callback_data="adm:texts"), InlineKeyboardButton("🟢 خدمات", callback_data="adm:services")],
        [InlineKeyboardButton("📊 گزارش کامل", callback_data="adm:report"), InlineKeyboardButton("📣 اعلان همگانی", callback_data="adm:announce")],
        [InlineKeyboardButton("🤖 بات‌های متصل", callback_data="adm:bots"), InlineKeyboardButton("🧾 لاگ مدیریت", callback_data="adm:logs")],
        [InlineKeyboardButton("🌙 همکاران شب‌کار", callback_data="night2:menu"), InlineKeyboardButton("⚙️ تنظیمات", callback_data="adm:settings")],
        [InlineKeyboardButton("⬅️ منوی اصلی", callback_data="adm:main")],
        [InlineKeyboardButton("🚪 خروج کامل از مدیریت", callback_data="adm:exit")],
    ])


def install(app, B):
    if getattr(B, "_final_admin_menu_fix", False):
        return True
    import telegram_admin_plus as A
    A._admin_menu = menu
    B.amenu = menu

    async def admin_text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not B.admin(user.id):
            return
        text = (msg.text or "").strip()
        if text not in ADMIN_LABELS:
            return
        await msg.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=menu())
        raise ApplicationHandlerStop

    async def admin_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("adm:") or not B.admin(q.from_user.id):
            return
        if q.data not in {"adm:menu"}:
            return
        await q.answer()
        await q.message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=menu())
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text), group=-20000)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^adm:menu$"), group=-20000)
    B._final_admin_menu_fix = True
    return True
