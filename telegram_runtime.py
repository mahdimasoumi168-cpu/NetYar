import os
import bot as B
from telegram.ext import MessageHandler, CallbackQueryHandler, filters


def advanced_amenu():
    return B.kb([
        ['👥 همکاران','➕ افزودن همکار'],
        ['💰 شارژها','💳 پرداخت‌های مشتری'],
        ['📋 درخواست‌ها','⚙️ قیمت‌ها'],
        ['📊 گزارش','🤖 افزودن بات'],
        ['🤖 بات‌های متصل','📣 اعلان خدمت'],
        ['⬅️ منوی اصلی']
    ])

B.amenu = advanced_amenu

async def extra_text(u,c):
    uid=u.effective_user.id
    st=B.S.setdefault(uid,{})
    # Persist the Telegram chat id after a partner logs in so status changes can be pushed automatically.
    if st.get('partner_id'):
        try:B.db.set_setting(f"partner_chat_{st['partner_id']}",str(u.effective_chat.id))
        except Exception:pass
    if not B.admin(uid):
        return
    t=(u.message.text or '').strip()
    step=st.get('extra_step')
    if t=='➕ افزودن همکار':
        st['extra_step']='partner'; return await u.message.reply_text('شماره، رمز و نام همکار را با فاصله بفرستید.\nمثال: 09991234567 123456 علی',reply_markup=B.amenu())
    if step=='partner':
        a=t.split(maxsplit=2)
        if len(a)<3:return await u.message.reply_text('❌ قالب نادرست است. مثال: 09991234567 123456 علی',reply_markup=B.amenu())
        try:B.db.add_partner(a[0],a[1],a[2]); st['extra_step']=None; return await u.message.reply_text('✅ همکار با موفقیت اضافه شد.',reply_markup=B.amenu())
        except Exception:return await u.message.reply_text('❌ ثبت همکار انجام نشد؛ احتمالاً شماره تکراری است.',reply_markup=B.amenu())
    if t=='🤖 افزودن بات':
        st['extra_step']='bot_platform'; return await u.message.reply_text('پیام‌رسان را انتخاب/ارسال کنید: telegram / rubika / bale / eitaa',reply_markup=B.amenu())
    if step=='bot_platform':
        p=t.lower().replace('تلگرام','telegram').replace('روبیکا','rubika').replace('بله','bale').replace('ایتا','eitaa')
        if p not in {'telegram','rubika','bale','eitaa'}:return await u.message.reply_text('❌ یکی از telegram / rubika / bale / eitaa را وارد کنید.',reply_markup=B.amenu())
        st['bot_platform']=p; st['extra_step']='bot_token'; return await u.message.reply_text('🔑 API Token بات را ارسال کنید.',reply_markup=B.amenu())
    if step=='bot_token':
        st['bot_token']=t; st['extra_step']='bot_name'; return await u.message.reply_text('🤖 نام بات را ارسال کنید.',reply_markup=B.amenu())
    if step=='bot_name':
        B.db.add_bot(st['bot_platform'],t,st['bot_token']); st['extra_step']=None; return await u.message.reply_text('✅ بات ثبت شد. اتصال در رجیستری ذخیره شد و آماده Adapter پیام‌رسان است.',reply_markup=B.amenu())
    if t=='🤖 بات‌های متصل':
        rows=B.db.bots(); txt='\n'.join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) or 'هیچ باتی ثبت نشده است.'
        return await u.message.reply_text(txt,reply_markup=B.amenu())
    if t=='📣 اعلان خدمت':
        st['extra_step']='done'; return await u.message.reply_text('🎫 کد پیگیری خدمتی که انجام شده را بفرستید.\nمثال: NYM-AB12CD34',reply_markup=B.amenu())
    if step=='done':
        r=B.db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(t,)).fetchone()
        if not r:return await u.message.reply_text('❌ کد پیگیری پیدا نشد.',reply_markup=B.amenu())
        B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(B.now(),r['id'])); B.db.conn.commit(); st['extra_step']=None
        # Notify the original Telegram customer automatically.
        customer_chat=None
        try:
            ur=B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram'",(r['user_id'],)).fetchone()
            if ur: customer_chat=ur['external_id']
        except Exception: pass
        if customer_chat:
            try:
                await c.bot.send_message(chat_id=customer_chat,text=f"🔔 خدمت شما بروزرسانی شد.\n🎫 کد پیگیری: {r['tracking_code']}\n📌 وضعیت جدید: انجام شد ✅")
            except Exception: pass
        partner_id=None
        pr=B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(r['id'],)).fetchone()
        if pr: partner_id=pr['answer']
        if partner_id:
            row=B.db.conn.execute("SELECT value FROM settings WHERE key=?",(f'partner_chat_{partner_id}',)).fetchone()
            if row and row['value']:
                try: await c.bot.send_message(chat_id=row['value'],text=f"🔔 وضعیت درخواست شما تغییر کرد.\n🎫 کد پیگیری: {r['tracking_code']}\n📌 وضعیت جدید: انجام شد ✅")
                except Exception: pass
        await u.message.reply_text(f'✅ خدمت {t} به‌عنوان انجام‌شده ثبت شد.',reply_markup=B.amenu())
        return

async def extra_cb(u,c):
    return


def build():
    app=B.build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, extra_text), group=-1)
    app.add_handler(CallbackQueryHandler(extra_cb), group=-1)
    return app

if __name__=='__main__':
    app=build()
    webhook=os.getenv('TELEGRAM_WEBHOOK_URL','').strip()
    if webhook:
        port=int(os.getenv('PORT','8080')); path=webhook.rstrip('/').split('/')[-1]
        app.run_webhook(listen='0.0.0.0',port=port,url_path=path,webhook_url=webhook,allowed_updates=None)
    else:
        app.run_polling(allowed_updates=None)
