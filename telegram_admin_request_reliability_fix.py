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
    def kb(rid):
        return InlineKeyboardMarkup([[InlineKeyboardButton('🔎 مشاهده اطلاعات کامل',callback_data=f'req:v:{rid}')],[InlineKeyboardButton('✅ تأیید خدمت',callback_data=f'req:a:{rid}'),InlineKeyboardButton('❌ رد خدمت',callback_data=f'req:x:{rid}')],[InlineKeyboardButton('🔐 درخواست کد از همکار',callback_data=f'req:p:{rid}')],[InlineKeyboardButton('🧩 درخواست کپچا',callback_data=f'req:captcha:{rid}'),InlineKeyboardButton('📝 درخواست نوشتار چکاپ',callback_data=f'req:checkup:{rid}')],[InlineKeyboardButton('💬 ارتباط با همکار',callback_data=f'req:chat:{rid}'),InlineKeyboardButton('📌 انتقال به آخر چت',callback_data=f'req:bottom:{rid}')],[InlineKeyboardButton('✉️ پاسخ',callback_data=f'req:r:{rid}')]])
    async def cb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        d=str(q.data or '')
        if d=='adm:partnerchat':
            rows=B.db.conn.execute('SELECT id,name,phone FROM partners WHERE active=1 ORDER BY id DESC').fetchall()
            buttons=[[InlineKeyboardButton(f"👤 {p['name'] or p['phone'] or p['id']}",callback_data=f'final:chat:{p["id"]}')] for p in rows]
            buttons.append([InlineKeyboardButton('⬅️ بازگشت',callback_data='adm:menu')])
            await q.answer(); await q.message.reply_text('💬 ارتباط با همکار\n\nهمکار موردنظر را انتخاب کنید:',reply_markup=InlineKeyboardMarkup(buttons)); raise ApplicationHandlerStop
        if d.startswith('req:r:'):
            try: rid=int(d.split(':')[-1])
            except Exception: return
            r=B.db.conn.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if not r: await q.answer('درخواست پیدا نشد',show_alert=True); raise ApplicationHandlerStop
            target=None
            try:
                u=B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram' LIMIT 1",(r['user_id'],)).fetchone()
                if u and str(u['external_id']).isdigit(): target=int(u['external_id'])
            except Exception: pass
            if not target:
                try: target=int(B.db.setting(f"partner_chat_{r['user_id']}",'') or 0) or None
                except Exception: pass
            if not target: await q.answer('گیرنده این درخواست پیدا نشد',show_alert=True); raise ApplicationHandlerStop
            B.S.setdefault(q.from_user.id,{}).update(mode='admin_reply_request',reply_target=target,reply_request_id=rid)
            await q.answer('آماده پاسخ'); await q.message.reply_text(f"✉️ پاسخ به درخواست {r['tracking_code']}\n\nمتن پاسخ را ارسال کنید.")
            raise ApplicationHandlerStop
    async def text(update,context):
        m=update.effective_message
        if not m or not B.admin(update.effective_user.id) or not m.text:return
        st=B.S.setdefault(update.effective_user.id,{})
        if st.get('mode')!='admin_reply_request':return
        try:
            await context.bot.send_message(chat_id=int(st['reply_target']),text='👔 پاسخ مدیریت\n\n'+m.text.strip())
            await m.reply_text('✅ پاسخ برای درخواست ارسال شد.',reply_markup=B.amenu())
        except Exception: await m.reply_text('❌ ارسال پاسخ انجام نشد.',reply_markup=B.amenu())
        st['mode']=None; raise ApplicationHandlerStop
    async def normalize(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id) or not str(q.data or '').startswith('req:'):return
        try: rid=int(str(q.data).split(':')[-1])
        except Exception:return
        try: await q.message.edit_reply_markup(reply_markup=kb(rid))
        except Exception: pass
    app.add_handler(CallbackQueryHandler(cb,pattern=r'^(adm:partnerchat|req:r:)'),group=-50000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-49999)
    app.add_handler(CallbackQueryHandler(normalize,pattern=r'^req:'),group=-49998)
    B._admin_request_reliability_fix=True
    return True
