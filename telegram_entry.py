import os
import requests
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters
import bot as corebot

ADMIN_IDS={x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}
ADMIN_CMD=os.getenv('ADMIN_COMMAND','/Admin2025').strip()

def is_admin(uid):
    # Keep the explicit administrator allow-list; the command alone never grants privileges.
    return str(uid) in ADMIN_IDS

def admin_menu():
    return corebot.kb([
        ['👥 همکاران','➕ افزودن همکار'],
        ['💰 شارژها','💳 پرداخت‌های مشتری'],
        ['📋 درخواست‌ها','⚙️ قیمت‌ها'],
        ['🤖 افزودن بات','🤖 مدیریت بات‌ها'],
        ['🔔 اعلان‌ها','📊 گزارش'],
        ['⬅️ منوی اصلی']
    ])

def validate_bot(platform, token):
    token=token.strip(); platform=platform.lower().strip()
    if platform=='telegram': url=f'https://api.telegram.org/bot{token}/getMe'; data={}
    elif platform=='rubika': url=f'https://botapi.rubika.ir/v3/{token}/getMe'; data={}
    elif platform=='bale': url=f'https://tapi.bale.ai/bot{token}/getMe'; data={}
    elif platform=='eitaa': url=f'https://eitaayar.ir/api/{token}/getMe'; data={}
    else: return False,'پلتفرم پشتیبانی نمی‌شود.'
    try:
        r=requests.post(url,json=data,timeout=15); r.raise_for_status(); body=r.json()
        ok=body.get('ok', True) if isinstance(body,dict) else False
        if not ok:return False,str(body.get('description') or body.get('error') or 'API token rejected')
        result=body.get('result') or body.get('data') or body
        name=(result.get('first_name') or result.get('bot_title') or result.get('username') or result.get('bot_id') or 'بات') if isinstance(result,dict) else 'بات'
        return True,str(name)
    except Exception as e:return False,str(e)[:180]

async def admin_command(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return await update.message.reply_text('⛔ دسترسی مدیریت ندارید.')
    corebot.S.setdefault(uid,{})['admin']=True
    corebot.S[uid]['admin_mode']=True
    await update.message.reply_text('🛠 پنل مدیریت پیشرفته کمک یار مهاجر\n\nگزینه موردنظر را انتخاب کنید:',reply_markup=admin_menu())

async def admin_router(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return False
    st=corebot.S.setdefault(uid,{})
    if not st.get('admin_mode') and not st.get('admin'): return False
    text=(update.message.text or '').strip()
    if text=='⬅️ منوی اصلی':
        st['admin_mode']=False; st['admin']=False
        return await update.message.reply_text('منوی اصلی',reply_markup=corebot.main(uid))
    if text=='👥 همکاران':
        rows=corebot.db.conn.execute('SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC').fetchall()
        msg='\n'.join(f"#{r['id']} | {r['name']} | {r['phone']} | {int(r['balance']):,} تومان | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or 'همکاری ثبت نشده است.'
        return await update.message.reply_text(msg,reply_markup=admin_menu())
    if text=='➕ افزودن همکار':
        st['admin_mode']=True; st['admin_step']='partner_phone'
        return await update.message.reply_text('📱 شماره همراه همکار را وارد کنید:',reply_markup=admin_menu())
    if st.get('admin_step')=='partner_phone':
        if not text.isdigit() or len(text)<10:return await update.message.reply_text('❌ شماره همراه معتبر نیست.')
        st['admin_phone']=text; st['admin_step']='partner_pass'; return await update.message.reply_text('🔐 رمز عبور همکار را وارد کنید:')
    if st.get('admin_step')=='partner_pass':
        st['admin_pass']=text; st['admin_step']='partner_name'; return await update.message.reply_text('👤 نام همکار را وارد کنید:')
    if st.get('admin_step')=='partner_name':
        try:
            corebot.db.add_partner(st['admin_phone'],st['admin_pass'],text or 'همکار')
            st.pop('admin_step',None); st.pop('admin_phone',None); st.pop('admin_pass',None)
            return await update.message.reply_text('✅ همکار با موفقیت تعریف شد.',reply_markup=admin_menu())
        except Exception:return await update.message.reply_text('❌ ثبت همکار انجام نشد؛ شماره احتمالاً قبلاً ثبت شده است.',reply_markup=admin_menu())
    if text=='🤖 افزودن بات':
        st['admin_step']='bot_platform'; return await update.message.reply_text('🤖 پیام‌رسان را انتخاب کنید: Telegram / Rubika / Bale / Eitaa',reply_markup=admin_menu())
    if st.get('admin_step')=='bot_platform':
        p=text.lower().replace('تلگرام','telegram').replace('روبیکا','rubika').replace('بله','bale').replace('ایتا','eitaa')
        if p not in {'telegram','rubika','bale','eitaa'}:return await update.message.reply_text('❌ یکی از Telegram / Rubika / Bale / Eitaa را وارد کنید.')
        st['bot_platform']=p;st['admin_step']='bot_token';return await update.message.reply_text('🔑 API Token ربات را ارسال کنید:')
    if st.get('admin_step')=='bot_token':
        ok,name=validate_bot(st['bot_platform'],text)
        if not ok:return await update.message.reply_text(f'❌ توکن/اتصال تأیید نشد.\n{name}')
        corebot.db.add_bot(st['bot_platform'],name,text)
        p=st['bot_platform'];st.pop('admin_step',None);st.pop('bot_platform',None)
        note='ثبت شد. برای Bale/Rubika اتصال ورودی در Worker مخصوص اجرا می‌شود؛ Eitaa فعلاً برای API ثبت و ارسال آماده است.' if p=='eitaa' else 'ثبت و اعتبارسنجی شد. ✅'
        return await update.message.reply_text(f'🤖 {p}\n👤 {name}\n\n{note}',reply_markup=admin_menu())
    if text=='🤖 مدیریت بات‌ها':
        rows=corebot.db.bots();msg='\n'.join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) or 'هیچ باتی ثبت نشده است.'
        return await update.message.reply_text(msg,reply_markup=admin_menu())
    if text=='🔔 اعلان‌ها':
        return await update.message.reply_text('🔔 اعلان خودکار فعال است: ثبت درخواست، رسید پرداخت، تأیید/رد پرداخت و تغییر وضعیت برای مدیر ثبت و در مسیر اعلان قابل اتصال است.',reply_markup=admin_menu())
    if text=='📊 گزارش':
        p=corebot.db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0];r=corebot.db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0];t=corebot.db.conn.execute("SELECT COUNT(*) FROM topups WHERE status='pending'").fetchone()[0]
        return await update.message.reply_text(f'📊 گزارش\n👥 همکاران: {p}\n📋 درخواست‌ها: {r}\n💰 شارژهای در انتظار: {t}',reply_markup=admin_menu())
    return False

def main():
    app=corebot.build()
    app.add_handler(CommandHandler('Admin2025',admin_command),group=-10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,admin_router),group=-10)
    webhook=os.getenv('TELEGRAM_WEBHOOK_URL','').strip()
    if webhook:
        port=int(os.getenv('PORT','8080')); path=webhook.rstrip('/').split('/')[-1]
        app.run_webhook(listen='0.0.0.0',port=port,url_path=path,webhook_url=webhook,allowed_updates=Update.ALL_TYPES)
    else: app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=='__main__':main()
