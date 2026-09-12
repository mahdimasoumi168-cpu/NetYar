"""Inline-only Telegram UI with deterministic callback routing."""
from types import SimpleNamespace
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler,ApplicationHandlerStop

def inline(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(str(x[0] if isinstance(x,(tuple,list)) else x),callback_data="ui2:"+str(x[0] if isinstance(x,(tuple,list)) else x)[:55]) for x in row] for row in rows if row])

def install(app,B):
    if getattr(B,"_inline_ui_v2",False):return
    B.kb=inline
    try:
        import telegram_business_features as F
        F._partner_kb=lambda: inline([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🔎 پیگیری کد","📋 سوابق"],["💰 موجودی","🎫 تیکت به مدیریت"],["🚪 خروج از پنل"],["❌ انصراف"]])
    except Exception:pass
    async def cb(update,context):
        q=update.callback_query
        if not q or not str(q.data or "").startswith("ui2:"):return
        label=q.data[4:];uid=q.from_user.id;await q.answer()
        class Msg:
            def __init__(self,src,text):self._src,self.text=src,text
            def __getattr__(self,n):return getattr(self._src,n)
        msg=Msg(q.message,label)
        proxy=SimpleNamespace(update_id=update.update_id,message=msg,effective_message=msg,effective_user=q.from_user,effective_chat=q.message.chat,callback_query=q)
        if label=="🔄 شروع مجدد":return await B.start(proxy,context)
        if label in {"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات","پنل مدیریت"} and B.admin(uid):
            try:
                import telegram_admin_plus as A
                return await A._callback(SimpleNamespace(callback_query=SimpleNamespace(data="adm:menu",from_user=q.from_user,message=q.message),effective_user=q.from_user),context,B)
            except Exception:return await q.message.reply_text("🛠 پنل مدیریت",reply_markup=B.amenu())
        if label=="👥 پنل همکاران":return await B.partner(proxy,context)
        if label=="❌ انصراف":return await B.cancel(proxy,context)
        # Existing router/feature layers own the service semantics.
        result=await B.router(proxy,context)
        if result is not None:raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^ui2:"),group=-10)
    B._inline_ui_v2=True
