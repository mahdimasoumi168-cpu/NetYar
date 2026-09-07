import re
import rubika_bot as rb

LANG_ALIASES = {
    'lang:fa':'fa','lang:en':'en','lang:ar':'ar',
    '1':'fa','2':'en','3':'ar',
    'فارسی':'fa','🇮🇷 فارسی':'fa','farsi':'fa','fa':'fa',
    'English':'en','🇬🇧 English':'en','english':'en','en':'en',
    'العربية':'ar','🇸🇦 العربية':'ar','arabic':'ar','ar':'ar',
}

def _lang_menu():
    return rb.buttons([[('lang:fa','🇮🇷 فارسی'),('lang:en','🇬🇧 English'),('lang:ar','🇸🇦 العربية')]])
rb.lang_menu=_lang_menu

def _lang_choice(text):
    raw=(text or '').strip()
    return LANG_ALIASES.get(raw) or LANG_ALIASES.get(raw.replace('🇮🇷 ','').replace('🇬🇧 ','').replace('🇸🇦 ',''))

def _set_language(uid, chat, lang):
    st=rb.new_state(uid)
    st['lang']=lang
    st['step']='citizenship'
    rb.send(chat, rb.TEXT[lang]['cit'], rb.citizenship_menu(lang))

def _partner_menu(lang='fa'):
    base=rb.partner_menu_original(lang)
    if lang=='en': return rb.buttons([[('1','➕ Top up'),('2','🔎 Track code')],[('3','📋 History'),('4','💰 Balance')],[('5','🏛 Government access issue')],[('0','❌ Cancel')]])
    if lang=='ar': return rb.buttons([[('1','➕ شحن الحساب'),('2','🔎 رمز المتابعة')],[('3','📋 السجل'),('4','💰 الرصيد')],[('5','🏛 حل مشكلة خدمات الحكومة')],[('0','❌ إلغاء')]])
    return rb.buttons([[('1','➕ شارژ حساب'),('2','🔎 پیگیری کد')],[('3','📋 سوابق'),('4','💰 موجودی')],[('5','🏛 حل مشکل ورود اتباع دولت من')],[('0',rb.CANCEL)]])
if not hasattr(rb,'partner_menu_original'):
    rb.partner_menu_original=rb.partner_menu
rb.partner_menu=_partner_menu

def _partner_gov_start(uid, chat):
    st=rb.STATES.setdefault(uid,{})
    st['step']='partner_gov_fida'
    st['gov_files']={}
    st['gov_started']=True
    rb.send(chat,'🪪 شناسه فیدا/کد اختصاصی مشتری را وارد کنید.',rb.buttons([[('0','❌ انصراف')]]))

def _partner_gov_confirm(uid, chat):
    st=rb.STATES[uid]
    lang=st.get('lang','fa')
    amount=int(rb.db.setting('price_government','500000') or 500000)
    p=rb.db.conn.execute('SELECT * FROM partners WHERE id=? AND active=1',(st.get('partner_id'),)).fetchone()
    if not p:
        rb.send(chat,'❌ نشست پنل همکاران معتبر نیست. لطفاً دوباره وارد پنل شوید.',rb.partner_menu(lang)); st['step']='partner_menu'; return
    if int(p['balance']) < amount:
        rb.send(chat,f'❌ اعتبار همکار کافی نیست.\n💰 هزینه خدمت: {amount:,} تومان\n💳 موجودی فعلی: {int(p["balance"]):,} تومان\nابتدا حساب را شارژ کنید.',rb.partner_menu(lang)); st['step']='partner_menu'; return
    cur=rb.db.conn.execute('UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND balance>=?',(amount,rb.now(),p['id'],amount))
    if cur.rowcount != 1:
        rb.db.conn.rollback(); rb.send(chat,'❌ کسر اعتبار انجام نشد. لطفاً دوباره تلاش کنید.',rb.partner_menu(lang)); st['step']='partner_menu'; return
    internal=rb.db.user('rubika',uid,'','')
    rid,code=rb.db.create_request(internal,'government','rubika',amount)
    rb.db.answer(rid,'partner_id',str(p['id']))
    rb.db.answer(rid,'fida',st.get('fida_id',''))
    rb.db.answer(rid,'yekta',st.get('yekta',''))
    rb.db.answer(rid,'customer_id_document','',st.get('gov_files',{}).get('id',''))
    rb.db.answer(rid,'sim_document','',st.get('gov_files',{}).get('sim',''))
    rb.db.answer(rid,'customer_mobile',st.get('customer_phone',''))
    rb.db.answer(rid,'customer_birth_date',st.get('dob',''))
    rb.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_wallet',updated_at=? WHERE id=?",(rb.now(),rid))
    rb.db.conn.commit()
    rb.db.audit('rubika',uid,'partner_government_request',code,f'partner={p["id"]};amount={amount}')
    rb.send(chat,f'✅ درخواست «حل مشکل ورود اتباع سامانه دولت من» با موفقیت ثبت شد.\n\n🎫 کد پیگیری: {code}\n💰 هزینه کسرشده از اعتبار: {amount:,} تومان\n💰 موجودی جدید: {int(p["balance"])-amount:,} تومان\n\nدرخواست برای انجام خدمت ارسال شد.',rb.partner_menu(lang))
    st['step']='partner_menu'; st.pop('gov_files',None); st.pop('gov_started',None)

_old_text=rb.handle_text
_old_media=rb.handle_media

def handle_text(uid, chat, text):
    st=rb.new_state(uid)
    step=st.get('step')
    if step=='language':
        chosen=_lang_choice(text)
        if chosen:
            _set_language(uid,chat,chosen); return
        rb.send(chat,rb.TEXT['fa']['lang'],rb.lang_menu()); return
    if step=='partner_menu':
        s=(text or '').strip()
        if s.startswith('5') or 'دولت من' in s or 'government' in s.lower() or 'الحكومة' in s:
            _partner_gov_start(uid,chat); return
    if step=='partner_gov_fida':
        if not text.strip() or rb.is_cancel(text): rb.cancel(uid,chat); return
        st['fida_id']=text.strip(); st['step']='partner_gov_yekta'
        rb.send(chat,'🔢 شناسه یکتای مشتری را وارد کنید.',rb.buttons([[('0','❌ انصراف')]])); return
    if step=='partner_gov_yekta':
        if not text.strip(): rb.send(chat,'🔢 شناسه یکتای مشتری را وارد کنید.',rb.buttons([[('0','❌ انصراف')]])); return
        st['yekta']=text.strip(); st['step']='partner_gov_id_doc'
        rb.send(chat,'🪪 تصویر مدرک شناسایی مشتری را ارسال کنید.',rb.buttons([[('0','❌ انصراف')]])); return
    if step=='partner_gov_sim_text':
        if text.strip().lower() in {'ندارم','no','no document','لا يوجد'}:
            st['gov_files']['sim']=''; st['step']='partner_gov_phone'
            rb.send(chat,'📱 شماره موبایل مشتری را وارد کنید. سیم‌کارت باید به نام خود مشتری باشد.',rb.buttons([[('0','❌ انصراف')]])); return
        rb.send(chat,'📄 لطفاً تصویر سند سیم‌کارت مشتری را ارسال کنید یا «ندارم» را بزنید.',rb.buttons([[('0','❌ انصراف')]])); return
    if step=='partner_gov_phone':
        phone=re.sub(r'\D','',text or '')
        if not re.fullmatch(r'09\d{9}',phone):
            rb.send(chat,'📱 شماره موبایل مشتری را به صورت صحیح وارد کنید؛ مثال: 09123456789',rb.buttons([[('0','❌ انصراف')]])); return
        st['customer_phone']=phone; st['step']='partner_gov_dob'
        rb.send(chat,'🎂 تاریخ تولد مشتری را به صورت 1356/01/01 وارد کنید.',rb.buttons([[('0','❌ انصراف')]])); return
    if step=='partner_gov_dob':
        if not re.fullmatch(r'1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])',text or ''):
            rb.send(chat,'🎂 تاریخ تولد مشتری را دقیقاً به صورت 1356/01/01 وارد کنید.',rb.buttons([[('0','❌ انصراف')]])); return
        st['dob']=text.strip(); st['step']='partner_gov_confirm'
        p=rb.db.conn.execute('SELECT balance FROM partners WHERE id=?',(st.get('partner_id'),)).fetchone()
        amount=int(rb.db.setting('price_government','500000') or 500000)
        rb.send(chat,f'📋 خلاصه درخواست «حل مشکل دولت من»\n\n🆔 فیدا/اختصاصی مشتری: {st.get("fida_id")}\n🔢 شناسه یکتا مشتری: {st.get("yekta")}\n📱 موبایل مشتری: {st.get("customer_phone")}\n🎂 تاریخ تولد مشتری: {st.get("dob")}\n\n💰 هزینه: {amount:,} تومان\n💳 اعتبار فعلی: {int(p["balance"]) if p else 0:,} تومان\n\nبرای ثبت نهایی «تأیید» و برای لغو «انصراف» را بزنید.',rb.buttons([[('1',rb.OK)],[('0',rb.CANCEL)]])); return
    if step=='partner_gov_confirm':
        if rb.is_confirm(text): _partner_gov_confirm(uid,chat); return
        if rb.is_cancel(text): rb.cancel(uid,chat); return
        rb.send(chat,'برای ثبت نهایی «تأیید» یا «انصراف» را انتخاب کنید.',rb.buttons([[('1',rb.OK)],[('0',rb.CANCEL)]])); return
    return _old_text(uid,chat,text)

def handle_media(uid,chat,msg):
    st=rb.new_state(uid); step=st.get('step'); fid=rb.media_id(msg)
    if step=='partner_gov_id_doc':
        if not fid: rb.send(chat,'🪪 لطفاً تصویر مدرک شناسایی مشتری را ارسال کنید.',rb.buttons([[('0','❌ انصراف')]])); return
        st.setdefault('gov_files',{})['id']=fid; st['step']='partner_gov_sim_text'
        rb.send(chat,'📄 اگر سند سیم‌کارت مشتری را دارید، تصویر آن را ارسال کنید؛ در غیر این صورت «ندارم» را بزنید.',rb.buttons([[('0','❌ انصراف')]])); return
    if step=='partner_gov_sim_text':
        if not fid: rb.send(chat,'📄 تصویر سند سیم‌کارت مشتری را ارسال کنید یا «ندارم» را بزنید.',rb.buttons([[('0','❌ انصراف')]])); return
        st.setdefault('gov_files',{})['sim']=fid; st['step']='partner_gov_phone'
        rb.send(chat,'📱 شماره موبایل مشتری را وارد کنید. سیم‌کارت باید به نام خود مشتری باشد.',rb.buttons([[('0','❌ انصراف')]])); return
    return _old_media(uid,chat,msg)

rb.handle_text=handle_text
rb.handle_media=handle_media

if __name__=='__main__':
    rb.run()
