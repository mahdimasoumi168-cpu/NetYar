"""Permanent Telegram restart button.
The ReplyKeyboard is persistent and survives normal inline-menu navigation.
The restart action clears transient flow state while preserving an active
partner session, then returns the user to the canonical start flow.
"""
from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, CommandHandler, filters, ApplicationHandlerStop

RESTART="🔄 شروع مجدد"

def _keyboard():
    return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)

def _clear_flow(st):
    keep={k:st[k] for k in ("partner_id","partner_active","partner_phone","partner_username","lang","status") if k in st}
    st.clear();st.update(keep);st["mode"]=None

def install(app,B):
    if getattr(B,"_permanent_restart_v1",False): return
    B.restart_keyboard=_keyboard
    async def restart(update,context):
        if not update.message:return
        text=(update.message.text or "").strip()
        if text not in {RESTART,"شروع مجدد"}:return
        uid=update.effective_user.id
        st=B.S.setdefault(uid,{})
        _clear_flow(st)
        try:
            await B.start(update,context)
        except Exception:
            await update.effective_message.reply_text("❌ شروع مجدد انجام نشد. دوباره تلاش کنید.",reply_markup=_keyboard())
        else:
            # B.start implementations can replace their own keyboard; immediately
            # re-assert the persistent bottom keyboard.
            await update.effective_message.reply_text("🔄 آماده‌اید. از منوی ربات استفاده کنید.",reply_markup=_keyboard())
        raise ApplicationHandlerStop
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,restart),group=-2000001)
    async def start_cmd(update,context):
        try:
            await B.start(update,context)
        finally:
            try: await update.effective_message.reply_text("",reply_markup=_keyboard())
            except Exception: pass
        raise ApplicationHandlerStop
    app.add_handler(CommandHandler("start",start_cmd),group=-2000001)
    B._permanent_restart_v1=True
