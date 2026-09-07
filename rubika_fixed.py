import os, time, logging, requests
from core import db, check_password

logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO)
log=logging.getLogger('netyar.rubika')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
BASE=f'https://botapi.rubika.ir/v3/{TOKEN}'
S={}
CANCEL='❌ انصراف'; OK='✅ تأیید'
TEXT={
'fa':{'lang':'🌐 زبان را انتخاب کنید:','cit':'آیا اتباع هستید یا ایرانی؟','iran':'🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.','menu':'سلام 👋\nخدمت موردنظر را انتخاب کنید:','track':'🎫 کد پیگیری را وارد کنید.','login_phone':'📱 شماره همراه همکار را وارد کنید.','login_pass':'🔐 رمز عبور همکار را وارد کنید.','bad_login':'❌ شماره همراه یا رمز عبور نادرست است.','no_partner':'❌ همکار پیدا نشد.','balance':'💰 موجودی اعتبار شما: {amount:,} تومان','cancel':'عملیات لغو شد. به منوی اصلی برگشتید. ✅','bad':'لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.','print':'🖨 نوع چاپ را انتخاب کنید:','side':'📄 نوع چاپ را انتخاب کنید:','copies':'🔢 تعداد نسخه موردنیاز از هر صفحه را وارد کنید.','files':'📎 فایل‌ها یا عکس‌ها را یکی‌یکی ارسال کنید. در پایان «تأیید» را بزنید.','fida':'🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.','fida_phone':'📱 شماره موبایل مشترک را وارد کنید.','gov_fida':'🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید.','gov_yekta':'🔢 شناسه یکتای مشترک را وارد کنید.','id':'🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.','phone':'📱 شماره موبایل مشترک را وارد کنید. سیم‌کارت باید به نام خود مشترک باشد.','dob':'🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.','doc':'📄 اگر سند سیم‌کارت دارید تصویر آن را ارسال کنید؛ در غیر این صورت «ندارم» را بزنید.'},
'en':{'lang':'🌐 Choose your language:','cit':'Are you a foreign national or Iranian?','iran':'🇮🇷 Services are currently unavailable for Iranian users.','menu':'Hello 👋\nChoose a service:','track':'🎫 Enter the tracking code.','login_phone':'📱 Enter your partner phone number.','login_pass':'🔐 Enter your partner password.','bad_login':'❌ Invalid phone or password.','no_partner':'❌ Partner not found.','balance':'💰 Your balance: {amount:,} toman','cancel':'Operation cancelled. Back to the main menu. ✅','bad':'Please choose one of the displayed options.','print':'🖨 Choose print type:','side':'📄 Choose printing mode:','copies':'🔢 Enter copies per page.','files':'📎 Send files/images one by one. Choose Confirm when finished.','fida':'🪪 Send the customer identification document.','fida_phone':'📱 Enter the customer mobile number.','gov_fida':'🆔 Enter the customer FIDA/special ID.','gov_yekta':'🔢 Enter the customer unique ID.','id':'🪪 Send the customer identification document.','phone':'📱 Enter the customer mobile number. The SIM must be registered to the customer.','dob':'🎂 Enter the customer birth date as 1356/01/01.','doc':'📄 Send the SIM ownership document, or choose No.'},
'ar':{'lang':'🌐 اختر اللغة:','cit':'هل أنت من الرعايا الأجانب أم إيراني؟','iran':'🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين.','menu':'مرحباً 👋\nاختر الخدمة:','track':'🎫 أدخل رمز المتابعة.','login_phone':'📱 أدخل رقم هاتف الشريك.','login_pass':'🔐 أدخل كلمة مرور الشريك.','bad_login':'❌ رقم الهاتف أو كلمة المرور غير صحيحة.','no_partner':'❌ لم يتم العثور على الشريك.','balance':'💰 رصيدك: {amount:,} تومان','cancel':'تم إلغاء العملية والعودة إلى القائمة الرئيسية. ✅','bad':'يرجى اختيار أحد الخيارات المعروضة.','print':'🖨 اختر نوع الطباعة:','side':'📄 اختر طريقة الطباعة:','copies':'🔢 أدخل عدد النسخ لكل صفحة.','files':'📎 أرسل الملفات أو الصور. عند الانتهاء اختر تأكيد.','fida':'🪪 أرسل صورة وثيقة هوية العميل.','fida_phone':'📱 أدخل رقم هاتف العميل.','gov_fida':'🆔 أدخل رقم فيدا/الرقم الخاص بالعميل.','gov_yekta':'🔢 أدخل المعرف الفريد للعميل.','id':'🪪 أرسل صورة وثيقة هوية العميل.','phone':'📱 أدخل رقم هاتف العميل. يجب أن تكون الشريحة مسجلة باسم العميل.','dob':'🎂 أدخل تاريخ الميلاد بالشكل 1356/01/01.','doc':'📄 أرسل وثيقة ملكية الشريحة أو اختر لا يوجد.'}}

def call(method,payload=None):
 r=requests.post(f'{BASE}/{method}',json=payload or {},timeout=35); r.raise_for_status(); b=r.json(); return b.get('data',b) if isinstance(b,dict) else b

def kb(rows): return [[(str(i),label) for i,label in row] for row in rows]
def send(chat,text,rows=None):
 p={'chat_id':str(chat),'text':text}
 if rows:
  p.update(chat_keypad_type='New',chat_keypad={'rows':[{'buttons':[{'id':i,'type':'Simple','button_text':label} for i,label in row]} for row in rows],'resize_keyboard':True,'one_time_keyboard':False})
 for n in range(3):
  try:return call('sendMessage',p)
  except requests.RequestException:
   if n==2: raise
   time.sleep(1+n)

def lang(uid): return S.get(uid,{}).get('lang','fa')
def T(uid,k,**kw): return TEXT[lang(uid)][k].format(**kw)
def lang_menu(): return kb([[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
def choose_lang(x): return {'1':'fa','2':'en','3':'ar','فارسی':'fa','🇮🇷 فارسی':'fa','English':'en','🇬🇧 English':'en','العربية':'ar','🇸🇦 العربية':'ar'}.get(x.strip())
def cit_menu(l): return kb([[('1','🪪 اتباع هستم' if l=='fa' else '🪪 Foreign national' if l=='en' else '🪪 أجنبي'),('2','🇮🇷 ایرانی هستم' if l=='fa' else '🇮🇷 Iranian' if l=='en' else '🇮🇷 إيراني')]])
def main(l):
 if l=='en': rows=[[('1','🪪 FIDA non-in-person'),('2','🖨 Printing')],[('3','🏛 Government access issue'),('4','🎫 Tracking')],[('5','📱 SIM services'),('6','📝 Screening & follow-up')],[('7','💰 My wallet'),('8','👥 Partner panel')],[('9','📞 Contact us'),('0','❌ Cancel')]]
 elif l=='ar': rows=[[('1','🪪 خدمة فيدا'),('2','🖨 الطباعة')],[('3','🏛 مشكلة خدمات الحكومة'),('4','🎫 متابعة')],[('5','📱 خدمات الشريحة'),('6','📝 الفحص والمتابعة')],[('7','💰 محفظتي'),('8','👥 لوحة الشركاء')],[('9','📞 اتصل بنا'),('0','❌ إلغاء')]]
 else: rows=[[('1','🪪 فیدای غیر حضوری'),('2','🖨 خدمات چاپ')],[('3','🏛 حل مشکل ورود اتباع دولت من'),('4','🎫 پیگیری')],[('5','📱 خدمات سیم کارت'),('6','📝 آزمون غربالگری و پیگیری')],[('7','💰 کیف پول من'),('8','👥 پنل همکاران')],[('9','📞 تماس با ما'),('0',CANCEL)]]
 return kb(rows)
def cancel(uid,chat):
 l=lang(uid); partner=S.get(uid,{}).get('partner_id'); S[uid]={'lang':l,'step':'menu','status':'foreign','partner_id':partner}; send(chat,T(uid,'cancel'),main(l))
def text_from(msg):
 x=str(msg.get('text') or '').strip()
 if x:return x
 a=msg.get('aux_data') or {}
 if isinstance(a,dict): return str(a.get('button_id') or '').strip()
 return ''
def file_id(msg):
 f=msg.get('file')
 if isinstance(f,dict) and f.get('file_id'): return str(f['file_id'])
 return str(msg.get('file_id') or '')
def handle(uid,chat,x):
 st=S.setdefault(uid,{'lang':'fa','step':'language'}); step=st.get('step'); l=st.get('lang','fa')
 if x in {CANCEL,'0','انصراف','لغو','Cancel','cancel','إلغاء'}: cancel(uid,chat); return
 if step=='language':
  z=choose_lang(x)
  if not z: send(chat,TEXT['fa']['lang'],lang_menu()); return
  st['lang']=z; st['step']='citizenship'; send(chat,TEXT[z]['cit'],cit_menu(z)); return
 if step=='citizenship':
  if x=='1': st['status']='foreign'; st['step']='menu'; send(chat,T(uid,'menu'),main(l)); return
  if x=='2': st['status']='iranian'; st['step']='iranian'; send(chat,T(uid,'iran'),kb([[('1','👥 پنل همکاران' if l=='fa' else '👥 Partner panel'),('2','🎫 پیگیری' if l=='fa' else '🎫 Track')]])); return
  send(chat,T(uid,'bad'),cit_menu(l)); return
 if step=='iranian':
  if x=='1': st['step']='partner_phone'; send(chat,T(uid,'login_phone'),kb([[('0','❌ Cancel')]])); return
  if x=='2': st['step']='track'; send(chat,T(uid,'track'),kb([[('0','❌ Cancel')]])); return
  send(chat,T(uid,'iran')); return
 if step=='menu':
  if x.startswith('1'): st['step']='fida_doc'; send(chat,T(uid,'fida'),kb([[('0','❌ Cancel')]])); return
  if x.startswith('2'): st['step']='print_color'; send(chat,T(uid,'print'),kb([[('1','⚫ سیاه و سفید' if l=='fa' else '⚫ Black & white' if l=='en' else '⚫ أبيض وأسود'),('2','🌈 رنگی' if l=='fa' else '🌈 Color' if l=='en' else '🌈 ملون')],[('0','❌ Cancel')]])); return
  if x.startswith('3'): st['step']='gov_fida'; send(chat,T(uid,'gov_fida'),kb([[('0','❌ Cancel')]])); return
  if x.startswith('4'): st['step']='track'; send(chat,T(uid,'track'),kb([[('0','❌ Cancel')]])); return
  if x.startswith('7'):
   p=st.get('partner_id'); row=db.conn.execute('SELECT balance FROM partners WHERE id=?',(p,)).fetchone() if p else None; send(chat,T(uid,'balance',amount=int(row['balance']) if row else 0),main(l)); return
  if x.startswith('8'): st['step']='partner_phone'; send(chat,T(uid,'login_phone'),kb([[('0','❌ Cancel')]])); return
  send(chat,T(uid,'menu'),main(l)); return
 if step=='partner_phone':
  p=db.partner(x)
  if not p: send(chat,T(uid,'no_partner')); return
  st['phone']=x; st['step']='partner_pass'; send(chat,T(uid,'login_pass'),kb([[('0','❌ Cancel')]])); return
 if step=='partner_pass':
  p=db.partner(st.get('phone',''))
  if not p or not check_password(x,p['password_hash']): send(chat,T(uid,'bad_login')); return
  st['partner_id']=p['id']; st['step']='partner_menu'; send(chat,T(uid,'balance',amount=int(p['balance'])),kb([[('1','➕ شارژ حساب'),('2','🔎 پیگیری کد')],[('3','📋 سوابق'),('4','💰 موجودی')],[('0','❌ انصراف')]])); return
 if step=='track':
  r=db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(x,)).fetchone(); send(chat,(f"🎫 {r['tracking_code']}\n📌 وضعیت: {r['status']}\n💳 پرداخت: {r['payment_status']}\n💰 مبلغ: {r['amount']:,} تومان" if r else '❌ کد پیگیری پیدا نشد.'),main(l)); st['step']='menu'; return
 if step=='print_color':
  if x not in {'1','2'}: send(chat,T(uid,'print')); return
  st['color']='bw' if x=='1' else 'color'; st['step']='print_side'; send(chat,T(uid,'side'),kb([[('1','📄 یک‌رو'),('2','🔄 پشت‌ورو')],[('0','❌ Cancel')]])); return
 if step=='print_side':
  if x not in {'1','2'}: send(chat,T(uid,'side')); return
  st['side']='single' if x=='1' else 'double'; st['step']='print_copies'; send(chat,T(uid,'copies'),kb([[('0','❌ Cancel')]])); return
 if step=='print_copies':
  if not x.isdigit() or int(x)<1: send(chat,T(uid,'copies')); return
  st['copies']=int(x); st['step']='print_files'; st['files']=[]; send(chat,T(uid,'files'),kb([[('1',OK)],[('0','❌ Cancel')]])); return
 if step=='partner_menu':
  if x.startswith('1'): st['step']='topup_amount'; send(chat,'💰 مبلغ شارژ را به تومان وارد کنید.',kb([[('0','❌ انصراف')]])); return
  if x.startswith('2'): st['step']='partner_track'; send(chat,T(uid,'track'),kb([[('0','❌ انصراف')]])); return
  if x.startswith('4'):
   p=db.conn.execute('SELECT balance FROM partners WHERE id=?',(st['partner_id'],)).fetchone(); send(chat,T(uid,'balance',amount=int(p['balance']) if p else 0)); return
  send(chat,T(uid,'bad'))
 if step=='topup_amount':
  import re
  try:a=int(re.sub(r'[^0-9]','',x))
  except:a=0
  if a<=0: send(chat,'💰 مبلغ شارژ را به تومان وارد کنید.'); return
  st['topup_amount']=a; st['step']='topup_receipt'; send(chat,f'💳 {a:,} تومان\nکارت: {db.setting("card_number")}\nبه نام: {db.setting("card_owner")}\n\n📸 رسید واریز را ارسال کنید.'); return
 if step=='partner_track':
  r=db.conn.execute('SELECT * FROM requests WHERE tracking_code=? AND user_id=?',(x,st['partner_id'])).fetchone(); send(chat,(f"🎫 {r['tracking_code']}\n📌 وضعیت: {r['status']}\n💰 مبلغ: {r['amount']:,} تومان" if r else '❌ کد پیگیری پیدا نشد.')); st['step']='partner_menu'; return
 if step=='fida_phone': st['phone']=x; send(chat,'✅ اطلاعات دریافت شد.'); st['step']='menu'; return
 if step=='gov_fida': st['fida_id']=x; st['step']='gov_yekta'; send(chat,T(uid,'gov_yekta')); return
 if step=='gov_yekta': st['yekta']=x; st['step']='gov_id'; send(chat,T(uid,'id')); return
 if step=='gov_phone': st['phone']=x; st['step']='gov_dob'; send(chat,T(uid,'dob')); return
 if step=='gov_dob': st['dob']=x; st['step']='menu'; send(chat,'✅ اطلاعات دریافت شد. درخواست برای بررسی ثبت می‌شود.',main(l)); return
 send(chat,T(uid,'bad'))

def media(uid,chat,msg):
 fid=file_id(msg); st=S.setdefault(uid,{'lang':'fa','step':'language'}); step=st.get('step')
 if not fid: send(chat,T(uid,'bad')); return
 if step=='fida_doc': st['doc']=fid; st['step']='fida_phone'; send(chat,T(uid,'fida_phone')); return
 if step=='gov_id': st['id_document']=fid; st['step']='gov_phone'; send(chat,T(uid,'phone')); return
 if step=='print_files': st.setdefault('files',[]).append(fid); send(chat,T(uid,'files'),kb([[('1',OK)],[('0','❌ Cancel')]])); return
 if step=='topup_receipt': db.add_topup(st['partner_id'],int(st['topup_amount']),fid); st['step']='partner_menu'; send(chat,'✅ رسید شارژ ثبت شد.',kb([[('1','➕ شارژ حساب'),('2','🔎 پیگیری کد')]])); return
 send(chat,T(uid,'bad'))

def process(upd):
 if not isinstance(upd,dict): return
 chat=str(upd.get('chat_id') or ''); msg=upd.get('new_message') or upd.get('updated_message') or {}
 if not chat or not isinstance(msg,dict) or msg.get('sender_type')=='Bot': return
 uid=chat
 if upd.get('type')=='StartedBot':
  if uid not in S:S[uid]={'lang':'fa','step':'language'}
  send(chat,TEXT['fa']['lang'],lang_menu()); return
 x=text_from(msg)
 if x=='/start': S[uid]={'lang':'fa','step':'language'}; send(chat,TEXT['fa']['lang'],lang_menu()); return
 if file_id(msg): media(uid,chat,msg); return
 handle(uid,chat,x)

def run():
 log.info('Rubika getMe OK: %s',call('getMe')); off=None; log.info('NetYar Rubika polling started')
 while True:
  try:
   p={'limit':20};
   if off:p['offset_id']=off
   d=call('getUpdates',p); ups=d.get('updates',[]) if isinstance(d,dict) else d
   for u in ups or []:
    try:process(u)
    except Exception:log.exception('Rubika update failed')
   if isinstance(d,dict) and d.get('next_offset_id'):off=str(d['next_offset_id'])
   time.sleep(.8)
  except Exception:log.exception('Rubika polling error');time.sleep(5)
if __name__=='__main__':run()
