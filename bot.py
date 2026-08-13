import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler

logging.basicConfig(level=logging.INFO)

NAME, PHONE, ID_CODE, CITY = range(4)

MAIN_MENU = [
    ["📝 ثبت نام", "🏢 خدمات دفتر"],
    ["🔎 پیگیری درخواست", "📢 اطلاعیه‌ها"],
    ["☎️ پشتیبانی", "ℹ️ درباره ما"],
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام و خوش آمدید 🌷\nبه ربات دفتر نت‌یار مهاجر خوش آمدید.",
        reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    )

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً نام و نام خانوادگی خود را وارد کنید:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("شماره موبایل خود را وارد کنید:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("کد اتباع یا کد شناسایی را وارد کنید:")
    return ID_CODE

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["id_code"] = update.message.text
    await update.message.reply_text("شهر محل سکونت خود را وارد کنید:")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text
    await update.message.reply_text(
        "ثبت‌نام اولیه شما با موفقیت انجام شد ✅\n"
        f"نام: {context.user_data['name']}\n"
        f"شهر: {context.user_data['city']}"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ثبت‌نام لغو شد.")
    return ConversationHandler.END

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📝 ثبت نام":
        return await register_start(update, context)
    if text == "🏢 خدمات دفتر":
        await update.message.reply_text("بخش خدمات دفتر به‌زودی تکمیل می‌شود.")
    elif text == "🔎 پیگیری درخواست":
        await update.message.reply_text("برای پیگیری، کد درخواست خود را ارسال کنید.")
    elif text == "📢 اطلاعیه‌ها":
        await update.message.reply_text("در حال حاضر اطلاعیه‌ای ثبت نشده است.")
    elif text == "☎️ پشتیبانی":
        await update.message.reply_text("برای پشتیبانی با دفتر تماس بگیرید.")
    elif text == "ℹ️ درباره ما":
        await update.message.reply_text("دفتر نت‌یار مهاجر؛ ارائه خدمات و راهنمایی به مراجعان.")
    return None

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")

    app = Application.builder().token(token).build()

    registration = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 ثبت نام$"), register_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            ID_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_id)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(registration)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    app.run_polling()

if __name__ == "__main__":
    main()
