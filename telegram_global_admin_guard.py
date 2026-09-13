"""High-priority owner for the stable adm:* admin controls."""
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop
log = logging.getLogger("netyar.telegram.global_admin_guard")
KNOWN={"menu","main","users","partners","topups","payments","requests","prices","priceup","pricedown","priceset","creditup","creditdown","texts","services","report","announce","bots","logs","settings"}
def install(app,B):
    if getattr(B,"_global_admin_guard",False): return True
    async def callback(update,context):
        q=getattr(update,"callback_query",None)
        if not q:return
        data=str(q.data or "")
        if not data.startswith("adm:") or not B.admin(q.from_user.id):return
        action=data.split(":",1)[1]
        if action.split(":",1)[0] not in KNOWN:return
        try:await q.answer()
        except Exception:pass
        try:
            import telegram_admin_plus as A
            await A._callback(update,context,B)
        except ApplicationHandlerStop: raise
        except Exception:
            log.exception("admin callback failed: %s",data)
            try:await q.message.reply_text("❌ اجرای این بخش با خطای موقت مواجه شد.\nوضعیت فعلی پنل مدیریت حفظ شد؛ لطفاً دوباره همین گزینه را بزنید.",reply_markup=B.amenu())
            except Exception:pass
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(callback,pattern=r"^adm:"),group=-65000)
    B._global_admin_guard=True
    return True
