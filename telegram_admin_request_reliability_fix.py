from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters


def install(app,B):
    if getattr(B,'_admin_request_reliability_fix',False): return True
    try:
        import telegram_admin_plus as A
        old=A._admin_menu
        def menu():
            base=old(); rows=[list(r) for r in getattr(base,'inline_keyboard',[])]
            if not any('ارتباط با همکار' in str(getattr(b,'text','')) for row in rows for b in row):
                rows.insert(max(0,len(rows)-1),[InlineKeyboardButton('💬 ارتباط با همکار',callback_data='adm:partnerchat')])
            return InlineKeyboardMarkup(rows)
        A._admin_menu=menu; B.amenu=menu
    except Exception: pass

    def kb(rid, paid=False):
        rows=[
            [InlineKeyboardButton('🔎 مشاهده اطلاعات کامل',callback_data=f'rq:detail:{rid}')],
            [InlineKeyboardButton('📨 درخواست کد از همکار',callback_data=f'rq:ask:{rid}')],
        ]
        if paid:
            rows.append([InlineKeyboardButton('⏳ بررسی اولیه',callback_data=f'rq:review:{rid}'),InlineKeyboardButton('✅ انجام شد',callback_data=f'rq:approve:{rid}')])
        else:
            rows.append([InlineKeyboardButton('💰 تأیید دریافت وجه',callback_data=f'rq:payconfirm:{rid}'),InlineKeyboardButton('⏳ بررسی اولیه',callback_data=f'rq:review:{rid}')])
        rows.extend([
            [InlineKeyboardButton('❌ رد درخواست',callback_data=f'rq:reject:{rid}')],
            [InlineKeyboardButton('💬 ارتباط با همکار',callback_data=f'req:chat:{rid}')],
            [InlineKeyboardButton('📌 انتقال به آخر چت',callback_data=f'req:bottom:{rid}'),InlineKeyboardButton('✉️ پاسخ',callback_data=f'req:r:{rid}')],
        ])
        return InlineKeyboardMarkup(rows)

    def request_target(r):
        target=None
        try:
            u=B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram' LIMIT 1",(r['user_id'],)).fetchone()
            if u and str(u['external_id']).isdigit(): target=int(u['external_id'])
        except Exception: pass
        if not target:
            try: target=int(B.db.setting(f"partner_chat_{r['user_id']}",'') or 0) or None
            except Exception: pass
        if not target:
            try:
                pid=B.db.setting(f"request_partner_{r['id']}",'')
                if str(pid).isdigit():
                    p=B.db.conn.execute("SELECT phone FROM partners WHERE id=? LIMIT 1",(int(pid),)).fetchone()
                    if p: target=int(B.db.setting(f"partner_chat_{p['phone']}",'') or 0) or None
            except Exception: pass
        return target

    async def cb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        d=str(q.data or '')
        if not d.startswith('req:'): return
        parts=d.split(':')
        if len(parts)<3:return
        try: rid=int(parts[-1])
        except Exception:
            await q.answer('درخواست نامعتبر است',show_alert=True); raise ApplicationHandlerStop
        r=B.db.conn.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        if not r:
            await q.answer('درخواست پیدا نشد',show_alert=True); raise ApplicationHandlerStop
        await q.answer()
        action=parts[1]
        if action=='chat':
            # The dedicated reliable partner-chat handler is registered at higher priority.
            # If this fallback receives the callback, report a deterministic error instead of silently doing nothing.
            await q.answer('ارتباط با همکار را دوباره بزنید؛ اتصال همکار در حال آماده‌سازی است.',show_alert=True)
            raise ApplicationHandlerStop
        if action=='r':
            target=request_target(r)
            if not target:
                await q.answer('گیرنده این درخواست پیدا نشد',show_alert=True); raise ApplicationHandlerStop
            B.S.setdefault(q.from_user.id,{}).update(mode='admin_reply_request',reply_target=target,reply_request_id=rid)
            await q.message.reply_text(f"✉️ پاسخ به درخواست {r['tracking_code']}\n\nمتن پاسخ را ارسال کنید.",reply_markup=kb(rid,str(r['payment_status'] or '').lower()=='paid')); raise ApplicationHandlerStop
        if action=='bottom':
            await q.message.reply_text(f"📌 درخواست {r['tracking_code']} در انتهای چت قرار گرفت.",reply_markup=kb(rid,str(r['payment_status'] or '').lower()=='paid')); raise ApplicationHandlerStop
        return

    async def text(update,context):
        m=update.effective_message
        if not m or not B.admin(update.effective_user.id) or not m.text:return
        st=B.S.setdefault(update.effective_user.id,{})
        if st.get('mode')!='admin_reply_request':return
        try:
            await context.bot.send_message(chat_id=int(st['reply_target']),text='👔 پاسخ مدیریت\n\n'+m.text.strip(),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✉️ پاسخ دادن',callback_data='chat:reply')],[InlineKeyboardButton('⬅️ بازگشت به پنل مدیریت',callback_data='chat:back')]]))
            await m.reply_text('✅ پاسخ برای درخواست ارسال شد.',reply_markup=kb(st.get('reply_request_id'),False) if st.get('reply_request_id') else B.amenu())
        except Exception:
            await m.reply_text('❌ ارسال پاسخ انجام نشد. لطفاً دوباره همین گزینه را بزنید.',reply_markup=B.amenu())
        st['mode']=None; st.pop('reply_target',None); st.pop('reply_request_id',None); raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb,pattern=r'^req:'),group=-49900)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-49899)
    B._admin_request_reliability_fix=True
    return True