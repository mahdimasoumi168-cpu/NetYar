"""Per-service global pricing editor for Telegram admin."""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters


def install(app,B):
    if getattr(B,'_service_pricing_installed',False): return
    import telegram_admin_plus as A
    old=A._admin_menu
    if not getattr(A,'_service_price_menu',False):
        def menu():
            m=old(); rows=[list(r) for r in m.inline_keyboard]
            rows.insert(max(0,len(rows)-1),[InlineKeyboardButton('🧾 قیمت تک‌تک خدمات',callback_data='adm:service_prices')])
            return InlineKeyboardMarkup(rows)
        A._admin_menu=menu; A._service_price_menu=True

    async def cb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        d=(q.data or '').split(':')
        if d[:2]!=['adm','service_prices']: return
        await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
        rows=B.db.conn.execute('SELECT key,name,price,active FROM services ORDER BY id').fetchall()
        buttons=[]
        for r in rows:
            buttons.append([InlineKeyboardButton(f"{r['name']} — {int(r['price'] or 0):,} تومان",callback_data=f"sp:pick:{r['key']}")])
        buttons.append([InlineKeyboardButton('⬅️ پنل مدیریت',callback_data='sp:back')])
        return await q.message.reply_text('🧾 قیمت تک‌تک خدمات\n\nخدمت را انتخاب کنید:',reply_markup=InlineKeyboardMarkup(buttons))

    async def spcb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        d=(q.data or '').split(':')
        if len(d)<2 or d[0]!='sp': return
        await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
        if d[1]=='back': st['admin_plus_mode']=None; return await q.message.reply_text('🛠 پنل مدیریت',reply_markup=A._admin_menu())
        if d[1]=='pick':
            key=':'.join(d[2:]); r=B.db.conn.execute('SELECT key,name,price FROM services WHERE key=?',(key,)).fetchone()
            if not r:return await q.message.reply_text('❌ خدمت پیدا نشد.')
            st.update(admin_service_key=key,admin_service_mode='price')
            return await q.message.reply_text(f"💰 {r['name']}\nقیمت فعلی: {int(r['price'] or 0):,} تومان\n\nقیمت جدید را وارد کنید یا برای افزایش/کاهش از گزینه‌های زیر استفاده کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('➕ افزایش',callback_data='sp:up'),InlineKeyboardButton('➖ کاهش',callback_data='sp:down')],[InlineKeyboardButton('⬅️ لیست خدمات',callback_data='adm:service_prices')]]))
        if d[1] in {'up','down'}:
            st['admin_service_mode']='delta'; st['admin_service_direction']=d[1]
            return await q.message.reply_text('🔢 مبلغ تغییر را به تومان وارد کنید:')

    async def text(update,context):
        if not update.message or not B.admin(update.effective_user.id): return
        st=B.S.setdefault(update.effective_user.id,{})
        mode=st.get('admin_service_mode')
        if mode not in {'price','delta'}: return
        t=re.sub(r'[٬,\s]','',(update.message.text or '').strip())
        if not t.isdigit(): return await update.message.reply_text('❌ فقط عدد وارد کنید.')
        n=int(t); key=st.get('admin_service_key')
        r=B.db.conn.execute('SELECT name,price FROM services WHERE key=?',(key,)).fetchone()
        if not r:return await update.message.reply_text('❌ خدمت پیدا نشد.')
        old=int(r['price'] or 0)
        new=(old+n if st.get('admin_service_direction')=='up' else max(0,old-n)) if mode=='delta' else n
        B.db.conn.execute('UPDATE services SET price=? WHERE key=?',(new,key)); B.db.conn.commit()
        st['admin_service_mode']=None; st['admin_service_direction']=None
        return await update.message.reply_text(f"✅ {r['name']}\nقیمت قبلی: {old:,} تومان\nقیمت جدید: {new:,} تومان",reply_markup=A._admin_menu())

    app.add_handler(CallbackQueryHandler(cb,pattern=r'^adm:service_prices$'),group=-40)
    app.add_handler(CallbackQueryHandler(spcb,pattern=r'^sp:'),group=-40)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-39)
    B._service_pricing_installed=True
