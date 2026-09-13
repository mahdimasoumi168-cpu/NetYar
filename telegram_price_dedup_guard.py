"""Prevents duplicate partner-price entry handlers from firing."""
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop


def install(app, B):
    async def cb(update, context):
        q=update.callback_query
        if not q or q.data!="adm:partner_price_adjust" or not B.admin(q.from_user.id):return
        await q.answer()
        B.S.setdefault(q.from_user.id,{})["mode"]="final_pp_partner"
        await q.message.reply_text("📈 قیمت ویژه همکار\n\nشناسه، شماره موبایل یا نام همکار را ارسال کنید:")
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^adm:partner_price_adjust$"),group=-10000)
