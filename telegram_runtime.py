import os
import bot as B
from telegram.ext import MessageHandler, CallbackQueryHandler, filters


def advanced_amenu():
    return B.kb([['👥 همکاران','➕ افزودن همکار'],['💰 شارژها','💳 پرداخت‌های مشتری'],['📋 درخواست‌ها','⚙️ قیمت‌ها'],['📊 گزارش','🤖 افزودن بات'],['🤖 بات‌های متصل','📣 اعلان خدمت'],['⬅️ منوی اصلی']])

def platform_kb():
    return B.kb([['🤖 Telegram','🤖 Rubika'],['🤖 Bale','🤖 Eitaa'],['⬅️ بازگشت']])

B.amenu=advanced_amenu

async def fixed_history(u,c):
    uid=u.effective_user.id; st=B.S.get(uid,{})
    if not st.get('partner_id'):
        return await u.message.reply_text(B.L(uid,'ابتدا وارد پنل همکاران شوید.','Please log in to the partner panel first.','يرجى تسجيل الدخول إلى لوحة الشركاء أولاً.'),reply_markup=B.main(uid))
    rows=B.db.conn.execute('SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20',(st['partner_id'],)).fetchall()
    text='\n'.join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,}" for r in rows) or 'سابقه‌ای نیست.'
    return await u.message.reply_text(text,reply_markup=B.partner_kb(st.get('lang','fa')))
B.phistory=fixed_history

async def extra_text(u,c):
    uid=u.effective_user.id; st=B.S.setdefault(uid,{})
    if st.get('partner_id'):
        try:B.db.set_setting(f"partner_chat_{st['partner_id']}",str(u.effective_chat.id))
        except Exception:pass
    t=(u.message.text or '').strip(); lang=st.get('lang','fa')
    partner_actions={'➕ Top up':'topup','➕ شحن الحساب':'topup','➕ شارژ حساب':'topup','🪪 Partner request':'gov','🪪 طلب الشريك':'gov','🪪 ثبت درخواست همکار':'gov','🔎 Track code':'track','🔎 رمز المتابعة':'track','🔎 پیگیری کد':'track','📋 History':'history','📋 السجل':'history','📋 سوابق':'history','💰 Balance':'balance','💰 الرصيد':'balance','💰 موجودی':'balance','🏛 حل مشکل سامانه دولت من':'gov'}
    if st.get('partner_id') and t in partner_actions:
        a=partner_actions[t]
        if a=='topup': return await B.topup(u,c)
        if a=='track': return await B.ptrack(u,c)
        if a=='history': return await fixed_history(u,c)
        if a=='gov': return await B.gov(u,c)
        if a=='balance':
            p=B.db.conn.execute('SELECT balance FROM partners WHERE id=?',(st['partner_id'],)).fetchone(); amount=f"{p['balance']:,}" if p else '0'
            return await u.message.reply_text({'fa':f'💰 موجودی کیف پول شما: {amount} تومان','en':f'💰 Your balance: {amount} toman','ar':f'💰 رصيدك: {amount} تومان'}[lang],reply_markup=B.partner_kb(lang))
    if st.get('mode')=='print_color':
        if t in ('⚫ سیاه و سفید','⚫ Black & White','⚫ أبيض وأسود'): st['color']='bw'
        elif t in ('🌈 رنگی','🌈 Color','🌈 ملون'): st['color']='color'
        else: return
        st['mode']='print_side'; return await u.message.reply_text(B.L(uid,'📄 یک‌رو یا 🔄 پشت‌ورو؟','📄 Single-sided or 🔄 double-sided?','📄 وجه واحد أم 🔄 وجهان؟'),reply_markup=B.kb([[B.L(uid,'📄 یک‌رو','📄 Single-sided','📄 وجه واحد'),B.L(uid,'🔄 پشت‌ورو','🔄 Double-sided','🔄 وجهان')],[B.L(uid,B.CANCEL,'❌ Cancel','❌ إلغاء')]]))
    if st.get('mode')=='print_side':
        if t in ('📄 یک‌رو','📄 Single-sided','📄 وجه واحد'): st['side']=1
        elif t in ('🔄 پشت‌ورو','🔄 Double-sided','🔄 وجهان'): st['side']=2
        else: return
        st['mode']='print_copies'; return await u.message.reply_text(B.L(uid,'🔢 تعداد نسخه موردنیاز از هر صفحه را وارد کنید.','🔢 Enter the number of copies per page.','🔢 أدخل عدد النسخ لكل صفحة.'),reply_markup=B.cancel_kb(lang))
    if st.get('mode')=='print' and t in ('✅ تأیید','✅ Confirm','✅ تأكيد'):
        old=u.message.text
        try:
            u.message.text=B.OK; return await B.service_text(u,c)
        finally:
            try:u.message.text=old
            except Exception:pass
    if not B.admin(uid): return
    step=st.get('extra_step')
    if t=='➕ افزودن همکار':
        st['extra_step']='partner'; return await u.message.reply_text('شماره، رمز و نام همکار را با فاصله بفرستید.\nمثال: 09991234567 123456 علی',reply_markup=B.amenu())
    if step=='partner':
        a=t.split(maxsplit=2)
        if len(a)<3:return await u.message.reply_text('❌ قالب نادرست است. مثال: 09991234567 123456 علی',reply_markup=B.amenu())
        try:B.db.add_partner(a[0],a[1],a[2]); st['extra_step']=None; return await u.message.reply_text('✅ همکار با موفقیت اضافه شد.',reply_markup=B.amenu())
        except Exception:return await u.message.reply_text('❌ ثبت همکار انجام نشد؛ احتمالاً شماره تکراری است.',reply_markup=B.amenu())
    if t=='🤖 افزودن بات':
        st['extra_step']='bot_platform'; return await u.message.reply_text('پیام‌رسان را انتخاب کنید یا نام آن را متنی ارسال کنید:',reply_markup=platform_kb())
    if step=='bot_platform':
        raw=t.lower().strip(); aliases={'🤖 telegram':'telegram','🤖 rubika':'rubika','🤖 bale':'bale','🤖 eitaa':'eitaa','تلگرام':'telegram','روبیکا':'rubika','بله':'bale','ایتا':'eitaa'}; p=aliases.get(raw,raw)
        if p not in {'telegram','rubika','bale','eitaa'}: return await u.message.reply_text('❌ یکی از Telegram / Rubika / Bale / Eitaa را انتخاب کنید.',reply_markup=platform_kb())
        st['bot_platform']=p; st['extra_step']='bot_token'; return await u.message.reply_text('🔑 API Token بات را ارسال کنید.',reply_markup=B.amenu())
    if step=='bot_token': st['bot_token']=t; st['extra_step']='bot_name'; return await u.message.reply_text('🤖 نام بات را ارسال کنید.',reply_markup=B.amenu())
    if step=='bot_name': B.db.add_bot(st['bot_platform'],t,st['bot_token']); st['extra_step']=None; return await u.message.reply_text('✅ بات ثبت شد.',reply_markup=B.amenu())
    if t=='🤖 بات‌های متصل':
        rows=B.db.bots(); txt='\n'.join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) or 'هیچ باتی ثبت نشده است.'; return await u.message.reply_text(txt,reply_markup=B.amenu())
    if t=='📣 اعلان خدمت': st['extra_step']='done'; return await u.message.reply_text('🎫 کد پیگیری خدمتی که انجام شده را بفرستید.\nمثال: NYM-AB12CD34',reply_markup=B.amenu())
    if step=='done':
        r=B.db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(t,)).fetchone()
        if not r:return await u.message.reply_text('❌ کد پیگیری پیدا نشد.',reply_markup=B.amenu())
        B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(B.now(),r['id'])); B.db.conn.commit(); st['extra_step']=None
        try:
            ur=B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram'",(r['user_id'],)).fetchone()
            if ur: await c.bot.send_message(chat_id=ur['external_id'],text=f"🔔 خدمت شما بروزرسانی شد.\n🎫 کد پیگیری: {r['tracking_code']}\n📌 وضعیت جدید: انجام شد ✅")
        except Exception: pass
        return await u.message.reply_text(f'✅ خدمت {t} به‌عنوان انجام‌شده ثبت شد.',reply_markup=B.amenu())

async def extra_cb(u,c):
    return

def build():
    app=B.build()
    # IMPORTANT: keep the extra compatibility handlers AFTER bot.py's main handlers.
    # A group=-1 handler here used to intercept every text/callback and prevent the main router.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,extra_text),group=1)
    app.add_handler(CallbackQueryHandler(extra_cb),group=1)
    return app

if __name__=='__main__':
    app=build(); webhook=os.getenv('TELEGRAM_WEBHOOK_URL','').strip()
    if webhook:
        port=int(os.getenv('PORT','8080')); path=webhook.rstrip('/').split('/')[-1]; app.run_webhook(listen='0.0.0.0',port=port,url_path=path,webhook_url=webhook,allowed_updates=None)
    else: app.run_polling(allowed_updates=None)
