"""Global full bot open/close gate for Telegram.
When bot_enabled=0, every non-admin update is stopped before service handlers.
Admins remain able to reopen the bot.
"""
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

KEY="bot_enabled"
def enabled(B):
    try:return str(B.db.setting(KEY,"1") or "1")=="1"
    except Exception:return True
def _admin(B,uid):
    try:return bool(B.admin(uid))
    except Exception:return False
def _closed_markup():
    from telegram import InlineKeyboardMarkup,InlineKeyboardButton
    return InlineKeyboardMarkup([])
async def _cb(update,context,B):
    q=update.callback_query
    if not q or enabled(B) or _admin(B,q.from_user.id): return
    await q.answer("🔒 ربات موقتاً بسته است.",show_alert=True)
    await q.message.reply_text("🔒 ربات در حال حاضر به‌طور کامل بسته است.\n\n🚫 هیچ خدمتی، ثبت درخواست یا ادامه فرایندی در این زمان امکان‌پذیر نیست.",reply_markup=_closed_markup())
    raise ApplicationHandlerStop
async def _msg(update,context,B):
    u=update.effective_user
    if not u or enabled(B) or _admin(B,u.id): return
    await update.effective_message.reply_text("🔒 ربات در حال حاضر به‌طور کامل بسته است.\n\n🚫 هیچ خدمتی، ثبت درخواست یا ادامه فرایندی در این زمان امکان‌پذیر نیست.")
    raise ApplicationHandlerStop
def install(app,B):
    if getattr(B,"_global_full_close_gate_v1",False): return True
    app.add_handler(CallbackQueryHandler(lambda u,c:_cb(u,c,B),pattern=r"^(?!adm:|global:).*"),group=-50000)
    app.add_handler(MessageHandler(filters.ALL,_msg),group=-49999)
    B._global_full_close_gate_v1=True
    return True
