from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

def install(app,B):
    if getattr(B,'_global_cancel_v4',False): return
    async def h(u,c):
        q=u.callback_query
        if not q:return
        d=str(q.data or '')
        prefixes=('govv7:cancel','govv6:cancel','govv3:cancel','govv2:cancel','gov:cancel','rq4:cancel:','rqcode:cancel:')
        if not d.startswith(prefixes):return
        st=B.S.setdefault(q.from_user.id,{})
        pid=st.get('partner_id'); active=bool(pid and st.get('partner_active'))
        st.clear(); st.update(status='foreign',lang='fa')
        await q.answer('عملیات لغو شد')
        if active:
            st.update(partner_id=pid,partner_active=True,mode=None)
            await q.message.reply_text('❌ عملیات لغو شد.\n\n👥 به پنل همکاران بازگشتید.',reply_markup=B.partner_kb('fa'))
        else:
            await q.message.reply_text('❌ عملیات لغو شد.',reply_markup=B.main(q.from_user.id))
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(h,pattern=r'^(?:govv7:cancel|govv6:cancel|govv3:cancel|govv2:cancel|gov:cancel|rq4:cancel:|rqcode:cancel:)'),group=-3000000)
    B._global_cancel_v4=True
