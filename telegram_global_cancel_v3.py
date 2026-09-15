"""Universal cancel v3; includes every current government/request-code cancel callback."""
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_global_cancel_v3",False): return
    async def cancel(u,c):
        q=u.callback_query
        if not q:return
        d=str(q.data or "")
        if not (d.startswith("govv7:cancel") or d.startswith("govv6:cancel") or d.startswith("govv3:cancel") or d.startswith("govv2:cancel") or d.startswith("gov:cancel") or d.startswith("rq4:cancel:") or d.startswith("rqcode:cancel:")):return
        uid=q.from_user.id;st=B.S.setdefault(uid,{});pid=st.get("partner_id");active=bool(pid and st.get("partner_active"));st.clear();st.update(status="foreign",lang="fa")
        if active:
            st.update(partner_id=pid,partner_active=True,mode=None);await q.answer("عملیات لغو شد");await q.message.reply_text("❌ عملیات لغو شد.\n\n👥 به پنل همکاران بازگشتید.",reply_markup=B.partner_kb("fa"))
        else:
            await q.answer("عملیات لغو شد");await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(cancel,pattern=r"^(?:govv7:cancel|govv6:cancel|govv3:cancel|govv2:cancel|gov:cancel|rq4:cancel:|rqcode:cancel:)"),group=-3000000)
    B._global_cancel_v3=True
