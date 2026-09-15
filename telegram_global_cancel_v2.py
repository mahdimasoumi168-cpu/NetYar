"""Universal high-priority cancel router for Telegram flows."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_global_cancel_v2",False): return
    async def cancel(update,context):
        q=update.callback_query
        if not q: return
        data=str(q.data or "")
        if not (data.endswith(":cancel") or data.endswith(":cancel_request") or data.startswith("rq4:cancel:") or data.startswith("rqcode:cancel:")):
            return
        uid=q.from_user.id
        st=B.S.setdefault(uid,{})
        pid=st.get("partner_id")
        # Preserve only the identity/session needed to return to the correct panel.
        lang="fa"
        active=bool(pid and st.get("partner_active"))
        st.clear()
        st["status"]="foreign"
        st["lang"]=lang
        if active:
            st["partner_id"]=pid
            st["partner_active"]=True
            st["mode"]=None
            await q.answer("عملیات لغو شد")
            await q.message.reply_text("❌ عملیات لغو شد.\n\n👥 به پنل همکاران بازگشتید.",reply_markup=B.partner_kb("fa"))
        else:
            await q.answer("عملیات لغو شد")
            await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    # This layer is intentionally registered before generic flow handlers.
    app.add_handler(CallbackQueryHandler(cancel,pattern=r"^(?:.*:cancel|.*:cancel_request|rq4:cancel:.*|rqcode:cancel:.*)$"),group=-2000000)
    B._global_cancel_v2=True
