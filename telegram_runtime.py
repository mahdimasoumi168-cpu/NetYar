import os
import bot as B
from telegram import ReplyKeyboardMarkup
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
    if not B.admin(uid):
        return
    st=B.S.setdefault(uid,{})
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
        st['bot_platform']=t.lower(); st['extra_step']='bot_token'; return await u.message.reply_text('🔑 API Token بات را ارسال کنید.',reply_markup=B.amenu())
    if step=='bot_token':
        st['bot_token']=t; st['extra_step']='bot_name'; return await u.message.reply_text('🤖 نام بات را ارسال کنید.',reply_markup=B.amenu())
    if step=='bot_name':
        B.db.add_bot(st['bot_platform'],t,st['bot_token']); st['extra_step']=None; return await u.message.reply_text('✅ بات ثبت شد. این اتصال در رجیستری بات‌ها ذخیره شد و برای Adapter پیام‌رسان مربوطه آماده است.',reply_markup=B.amenu())
    if t=='🤖 بات‌های متصل':
        rows=B.db.bots(); txt='\n'.join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) or 'هیچ باتی ثبت نشده است.'
        return await u.message.reply_text(txt,reply_markup=B.amenu())
    if t=='📣 اعلان خدمت':
        st['extra_step']='done'; return await u.message.reply_text('🎫 کد پیگیری خدمتی که انجام شده را بفرستید.\nمثال: NYM-AB12CD34',reply_markup=B.amenu())
    if step=='done':
        r=B.db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(t,)).fetchone()
        if not r:return await u.message.reply_text('❌ کد پیگیری پیدا نشد.',reply_markup=B.amenu())
        B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(B.now(),r['id'])); B.db.conn.commit(); st['extra_step']=None
        await u.message.reply_text(f'✅ خدمت {t} به‌عنوان انجام‌شده ثبت شد.',reply_markup=B.amenu())
        return

async def extra_cb(u,c):
    return


def build():
    app=B.build()
    # Group -1 runs before the original generic text router, so admin-only extensions are not swallowed.
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
