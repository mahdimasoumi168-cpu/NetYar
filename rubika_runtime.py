import os, time, logging, re, requests
from core import db, now, check_password

logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO)
log=logging.getLogger('netyar.rubika')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
BASE=f'https://botapi.rubika.ir/v3/{TOKEN}'
HTTP=requests.Session(); HTTP.headers.update({'Content-Type':'application/json'})
CANCEL='❌ انصراف'; OK='✅ تأیید'; ADMIN_COMMAND=os.getenv('ADMIN_COMMAND','/Admin2025').strip()
ADMIN_IDS={x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}
S={}
TEXT={
'fa':{'lang':'🌐 زبان را انتخاب کنید:','cit':'آیا اتباع هستید یا ایرانی؟','iran':'🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.','menu':'سلام 👋\nخدمت موردنظر را انتخاب کنید:','phone':'📱 شماره موبایل مشترک را وارد کنید.','dob':'🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.','track':'🎫 کد پیگیری را وارد کنید.','bad':'لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.','cancel':'عملیات لغو شد. به منوی اصلی برگشتید. ✅'},
'en':{'lang':'🌐 Choose your language:','cit':'Are you a foreign national or Iranian?','iran':'🇮🇷 Services are currently unavailable for Iranian users.','menu':'Hello 👋\nChoose a service:','phone':"📱 Enter the customer's mobile number.",'dob':"🎂 Enter the customer's birth date as 1356/01/01.",'track':'🎫 Enter the tracking code.','bad':'Please choose one of the displayed options.','cancel':'Operation cancelled. Back to the main menu. ✅'},
'ar':{'lang':'🌐 اختر اللغة:','cit':'هل أنت من الرعايا الأجانب أم إيراني؟','iran':'🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين.','menu':'مرحباً 👋\nاختر الخدمة:','phone':'📱 أدخل رقم هاتف العميل.','dob':'🎂 أدخل تاريخ الميلاد بالشكل 1356/01/01.','track':'🎫 أدخل رمز المتابعة.','bad':'يرجى اختيار أحد الخيارات المعروضة.','cancel':'تم إلغاء العملية والعودة إلى القائمة الرئيسية. ✅'}}

def buttons(rows): return [[(str(i),label) for i,label in row] for row in rows]
def call(method,payload=None):
 r=HTTP.post(f'{BASE}/{method}',json=payload or {},timeout=35); r.raise_for_status(); b=r.json(); return b.get('data',b) if isinstance(b,dict) else b
def send(chat,text,keypad=None):
 p={'chat_id':str(chat),'text':text}
 if keypad:
  p['chat_keypad_type']='New'; p['chat_keypad']={'rows':[{'buttons':[{'id':b[0],'type':'Simple','button_text':b[1]} for b in row]} for row in keypad],'resize_keyboard':True,'one_time_keyboard':False}
 for n in range(3):
  try:return call('sendMessage',p)
  except requests.RequestException:
   if n==2: raise
   time.sleep(1.5*(n+1))
def lang_menu(): return buttons([[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
def cit_menu(lang):
 if lang=='en':return buttons([[('1','🪪 Foreign national'),('2','🇮🇷 Iranian')]])
 if lang=='ar':return buttons([[('1','🪪 أجنبي'),('2','🇮🇷 إيراني')]])
 return buttons([[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')]])
def main_menu(lang):
 if lang=='en': return buttons([[('1','🪪 FIDA non-in-person'),('2','🖨 Printing')],[('3','🏛 Government access issue'),('4','🎫 Tracking')],[('5','📱 SIM services'),('6','📝 Screening & follow-up')],[('7','💰 My wallet'),('8','👥 Partner panel')],[('0','❌ Cancel')]])
 if lang=='ar': return buttons([[('1','🪪 خدمة فيدا'),('2','🖨 الطباعة')],[('3','🏛 مشكلة خدمات الحكومة'),('4','🎫 متابعة')],[('5','📱 خدمات الشريحة'),('6','📝 الفحص والمتابعة')],[('7','💰 محفظتي'),('8','👥 لوحة الشركاء')],[('0','❌ إلغاء')]])
 return buttons([[('1','🪪 فیدای غیر حضوری'),('2','🖨 خدمات چاپ')],[('3','🏛 حل مشکل ورود اتباع دولت من'),('4','🎫 پیگیری')],[('5','📱 خدمات سیم کارت'),('6','📝 آزمون غربالگری و پیگیری')],[('7','💰 کیف پول من'),('8','👥 پنل همکاران')],[('0',CANCEL)]])
def partner_menu(lang):
 if lang=='en':return buttons([[('1','➕ Top up'),('2','🔎 Track code')],[('3','📋 History'),('4','💰 Balance')],[('5','🏛 Government access issue'),('0','❌ Cancel')]])
 if lang=='ar':return buttons([[('1','➕ شحن الحساب'),('2','🔎 رمز المتابعة')],[('3','📋 السجل'),('4','💰 الرصيد')],[('5','🏛 حل مشكلة الحكومة'),('0','❌ إلغاء')]])
 return buttons([[('1','➕ شارژ حساب'),('2','🔎 پیگیری کد')],[('3','📋 سوابق'),('4','💰 موجودی')],[('5','🏛 حل مشکل ورود اتباع دولت من'),('0',CANCEL)]])
def admin_menu(): return buttons([[('1','👥 همکاران'),('2','💰 شارژها')],[('3','💳 پرداخت‌ها'),('4','📋 درخواست‌ها')],[('5','⚙️ قیمت‌ها'),('6','📊 گزارش')],[('7','🤖 افزودن بات'),('8','🤖 بات‌های متصل')],[('9','📣 اعلان خدمت'),('10','➕ افزودن همکار')],[('0','🚪 خروج')]])
def text(uid,key): return TEXT.get(S.get(uid,{}).get('lang','fa'),TEXT['fa'])[key]
def is_admin(uid): return str(uid) in ADMIN_IDS or S.get(uid,{}).get('admin') is True
def cancel(uid,chat):
 lang=S.get(uid,{}).get('lang','fa'); partner=S.get(uid,{}).get('partner_id'); S[uid]={'lang':lang,'step':'partner_menu' if partner else 'menu','partner_id':partner} ; send(chat,text(uid,'cancel'),partner_menu(lang) if partner else main_menu(lang))
def msg_payload(u): return u.get('new_message') or u.get('updated_message') or {}
def msg_text(m):
 t=str(m.get('text') or '').strip()
 if t:return t
 a=m.get('aux_data') or {}
 if isinstance(a,dict): return str(a.get('button_id') or a.get('button_id_string') or '').strip()
 return ''
def media_id(m):
 for k in ('file','photo','image','document'):
  v=m.get(k)
  if isinstance(v,dict) and v.get('file_id'):return str(v['file_id'])
  if isinstance(v,str) and v:return v
 return str(m.get('file_id') or '')
def new(uid):return S.setdefault(uid,{'lang':'fa','step':'language'})
def amount(key,default=0): return int(db.setting('price_'+key,str(default)) or default)
def invoice(uid,chat,rid,code,a,menu):
 S[uid].update({'request_id':rid,'code':code,'step':'payment'}); send(chat,f'🧾 فاکتور\n🎫 کد پیگیری: {code}\n💰 مبلغ: {a:,} تومان\n\n💳 شماره کارت: {db.setting("card_number")}\nبه نام: {db.setting("card_owner")}\n\nپس از واریز، رسید را ارسال کنید.',menu)
def create(uid,key,a): return db.create_request(db.user('rubika',uid,'',''),'rubika' if False else key,'rubika',a)
def admin_notify(code,key,a):
 for x in ADMIN_IDS:
  try: send(x,f'🔔 درخواست جدید\n🎫 {code}\n🛠 خدمت: {key}\n💰 مبلغ: {a:,} تومان',admin_menu())
  except Exception: log.exception('admin notification failed')
def finish_request(uid,chat):
 st=S[uid]; r=db.conn.execute('SELECT * FROM requests WHERE id=?',(st.get('request_id'),)).fetchone()
 if not r:return
 db.conn.execute("UPDATE requests SET status='completed',payment_status='paid',updated_at=? WHERE id=?",(now(),r['id']));db.conn.commit(); send(chat,f'✅ خدمت شما با موفقیت انجام شد.\n🎫 کد پیگیری: {r["tracking_code"]}',main_menu(st.get('lang','fa'))); S[uid]['step']='menu'
def process_text(uid,chat,t):
 st=new(uid); step=st.get('step'); lang=st.get('lang','fa')
 if t==ADMIN_COMMAND: st['admin']=True;st['step']='admin';send(chat,'🛠 پنل مدیریت کامل بات',admin_menu());return
 if is_admin(uid) and step=='admin':
  if t in {'0','🚪 خروج'}:st['admin']=False;st['step']='menu';send(chat,'خروج از پنل مدیریت انجام شد.',main_menu(lang));return
  if t in {'1','👥 همکاران'}:
   rows=db.conn.execute('SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC').fetchall();send(chat,'\n'.join(f"#{r['id']} | {r['name']} | {r['phone']} | {int(r['balance']):,} تومان" for r in rows) or 'همکاری ثبت نشده.',admin_menu());return
  if t in {'2','💰 شارژها'}:
   rows=db.conn.execute('SELECT t.id,t.amount,t.status,p.name FROM topups t JOIN partners p ON p.id=t.partner_id ORDER BY t.id DESC LIMIT 30').fetchall();send(chat,'\n'.join(f"#{r['id']} | {r['name']} | {int(r['amount']):,} | {r['status']}" for r in rows) or 'شارژی نیست.',admin_menu());return
  if t in {'3','💳 پرداخت‌ها'}:
   rows=db.conn.execute("SELECT id,tracking_code,service_key,amount,payment_status FROM requests WHERE payment_status='pending' ORDER BY id DESC LIMIT 30").fetchall();send(chat,'\n'.join(f"#{r['id']} | {r['tracking_code']} | {r['service_key']} | {int(r['amount']):,}" for r in rows) or 'پرداخت معلقی نیست.',admin_menu());return
  if t in {'4','📋 درخواست‌ها'}:
   rows=db.conn.execute('SELECT tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 50').fetchall();send(chat,'\n'.join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,} | {r['payment_status']}" for r in rows) or 'درخواستی نیست.',admin_menu());return
  if t in {'5','⚙️ قیمت‌ها'}:st['step']='admin_price';send(chat,'قیمت را بفرستید؛ مثال: government 500000',admin_menu());return
  if t in {'6','📊 گزارش'}:
   p=db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0];q=db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0];send(chat,f'📊 گزارش\n👥 همکاران: {p}\n📋 درخواست‌ها: {q}',admin_menu());return
  if t in {'7','🤖 افزودن بات'}:st['step']='admin_bot_platform';send(chat,'نوع پیام‌رسان را بفرستید: telegram / rubika / bale / eitaa',admin_menu());return
  if t in {'8','🤖 بات‌های متصل'}:
   rows=db.bots();send(chat,'\n'.join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {r['status']} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or 'باتی ثبت نشده.',admin_menu());return
  if t in {'9','📣 اعلان خدمت'}:st['step']='admin_done';send(chat,'کد پیگیری خدمتی که انجام شده را بفرستید؛ مثال NYM-AB12CD34',admin_menu());return
  if t in {'10','➕ افزودن همکار'}:st['step']='admin_partner';send(chat,'شماره، رمز و نام را با فاصله بفرستید؛ مثال: 0912... 123456 علی',admin_menu());return
  if st.get('step')=='admin_price':
   a=t.split();
   if len(a)==2 and a[1].isdigit():db.set_setting('price_'+a[0],a[1]);st['step']='admin';send(chat,'✅ قیمت ذخیره شد.',admin_menu());return
  if st.get('step')=='admin_bot_platform':st['bot_platform']=t.lower();st['step']='admin_bot_token';send(chat,'API Token را بفرستید.',admin_menu());return
  if st.get('step')=='admin_bot_token':st['bot_token']=t;st['step']='admin_bot_name';send(chat,'نام بات را بفرستید.',admin_menu());return
  if st.get('step')=='admin_bot_name':
   db.add_bot(st['bot_platform'],t,st['bot_token']);st['step']='admin';send(chat,'✅ بات ثبت شد. برای اجرای واقعی هر پیام‌رسان، Adapter همان API روی Worker فعال می‌شود.',admin_menu());return
  if st.get('step')=='admin_partner':
   a=t.split(maxsplit=2)
   if len(a)<3:send(chat,'فرمت نادرست است.',admin_menu());return
   try:db.add_partner(a[0],a[1],a[2]);send(chat,'✅ همکار اضافه شد.',admin_menu())
   except Exception:send(chat,'❌ شماره تکراری یا اطلاعات نامعتبر است.',admin_menu())
   st['step']='admin';return
  if st.get('step')=='admin_done':
   r=db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(t,)).fetchone()
   if not r:send(chat,'❌ کد پیدا نشد.',admin_menu());return
   db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(now(),r['id']));db.conn.commit();
   send(chat,f'✅ درخواست {t} انجام‌شده ثبت شد.',admin_menu())
   return
  return
 if step=='language':
  m={'1':'fa','2':'en','3':'ar','فارسی':'fa','🇮🇷 فارسی':'fa','English':'en','🇬🇧 English':'en','العربية':'ar','🇸🇦 العربية':'ar'}; ch=m.get(t)
  if not ch:send(chat,TEXT['fa']['lang'],lang_menu());return
  st['lang']=ch;st['step']='citizenship';send(chat,TEXT[ch]['cit'],cit_menu(ch));return
 if step=='citizenship':
  if t.startswith('1') or 'اتباع' in t or 'Foreign' in t or 'أجنبي' in t:st['status']='foreign';st['step']='menu';send(chat,text(uid,'menu'),main_menu(lang));return
  if t.startswith('2') or 'ایرانی' in t or 'Iranian' in t or 'إيراني' in t:st['status']='iranian';st['step']='iranian';send(chat,text(uid,'iran'),buttons([[('1','👥 پنل همکاران'),('2','🎫 پیگیری')],[('0',CANCEL)]]));return
  send(chat,text(uid,'bad'),cit_menu(lang));return
 if step=='iranian':
  if t.startswith('1'):st['step']='partner_phone';send(chat,'📱 شماره همراه همکار را وارد کنید.',buttons([[('0',CANCEL)]]));return
  if t.startswith('2'):st['step']='track';send(chat,text(uid,'track'),buttons([[('0',CANCEL)]]));return
 if step=='menu':
  if t.startswith('1'):st['step']='fida_doc';send(chat,'🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.',buttons([[('0',CANCEL)]]));return
  if t.startswith('2'):st['step']='print_color';send(chat,'🖨 نوع چاپ را انتخاب کنید.',buttons([[('1','⚫ سیاه و سفید'),('2','🌈 رنگی')],[('0',CANCEL)]]));return
  if t.startswith('3'):st['step']='gov_fida';send(chat,'🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید.',buttons([[('0',CANCEL)]]));return
  if t.startswith('4'):st['step']='track';send(chat,text(uid,'track'),buttons([[('0',CANCEL)]]));return
  if t.startswith('8'):st['step']='partner_phone';send(chat,'📱 شماره همراه همکار را وارد کنید.',buttons([[('0',CANCEL)]]));return
  send(chat,text(uid,'bad'),main_menu(lang));return
 if step=='track':
  r=db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(t,)).fetchone();send(chat,(f"🎫 {r['tracking_code']}\n📌 وضعیت: {r['status']}\n💳 پرداخت: {r['payment_status']}\n💰 مبلغ: {int(r['amount']):,} تومان" if r else '❌ کد پیگیری پیدا نشد.'),main_menu(lang));st['step']='menu';return
 if step=='partner_phone':
  p=db.partner(t)
  if not p:send(chat,'❌ همکار پیدا نشد.',buttons([[('0',CANCEL)]]));return
  st['phone']=t;st['step']='partner_pass';send(chat,'🔐 رمز عبور همکار را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='partner_pass':
  p=db.partner(st.get('phone',''))
  if not p or not check_password(t,p['password_hash']):send(chat,'❌ شماره یا رمز عبور نادرست است.',buttons([[('0',CANCEL)]]));return
  st['partner_id']=p['id'];st['step']='partner_menu';send(chat,f"👥 پنل همکاران\n👤 {p['name']}\n💰 اعتبار: {int(p['balance']):,} تومان",partner_menu(lang));return
 if step=='partner_menu':
  if t.startswith('1'):st['step']='topup_amount';send(chat,'💰 مبلغ شارژ را به تومان وارد کنید.',buttons([[('0',CANCEL)]]));return
  if t.startswith('2'):st['step']='partner_track';send(chat,text(uid,'track'),buttons([[('0',CANCEL)]]));return
  if t.startswith('3'):
   rows=db.conn.execute('SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20',(st['partner_id'],)).fetchall();send(chat,'\n'.join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,}" for r in rows) or 'سابقه‌ای نیست.',partner_menu(lang));return
  if t.startswith('4'):
   p=db.conn.execute('SELECT balance FROM partners WHERE id=?',(st['partner_id'],)).fetchone();send(chat,f"💰 موجودی: {int(p['balance']) if p else 0:,} تومان",partner_menu(lang));return
  if t.startswith('5'):st['step']='partner_gov_fida';send(chat,'🆔 فیدا/کد اختصاصی مشتری را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='partner_track':
  r=db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(t,)).fetchone();send(chat,(f"🎫 {r['tracking_code']}\n📌 وضعیت: {r['status']}\n💰 {int(r['amount']):,} تومان" if r else '❌ کد پیدا نشد.'),partner_menu(lang));st['step']='partner_menu';return
 if step=='topup_amount':
  a=int(re.sub(r'\D','',t) or 0)
  if a<=0:send(chat,'❌ مبلغ نامعتبر است.',buttons([[('0',CANCEL)]]));return
  st['topup_amount']=a;st['step']='topup_receipt';send(chat,f'💳 {a:,} تومان\n💳 شماره کارت: {db.setting("card_number")}\nبه نام: {db.setting("card_owner")}\n📸 رسید را ارسال کنید.',buttons([[('0',CANCEL)]]));return
 if step=='fida_phone':
  ph=re.sub(r'\D','',t)
  if not re.fullmatch(r'09\d{9}',ph):send(chat,'📱 شماره موبایل مشترک را صحیح وارد کنید.',buttons([[('0',CANCEL)]]));return
  a=amount('fida',0);rid,code=create(uid,'fida',a);db.answer(rid,'document',file_id=st.get('doc',''));db.answer(rid,'phone',ph);admin_notify(code,'fida',a);invoice(uid,chat,rid,code,a,main_menu(lang));return
 if step=='gov_fida':st['fida']=t;st['step']='gov_yekta';send(chat,'🔢 شناسه یکتای مشترک را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='gov_yekta':st['yekta']=t;st['step']='gov_id';send(chat,'🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.',buttons([[('0',CANCEL)]]));return
 if step=='gov_phone':
  ph=re.sub(r'\D','',t)
  if not re.fullmatch(r'09\d{9}',ph):send(chat,'📱 شماره موبایل مشترک را صحیح وارد کنید.',buttons([[('0',CANCEL)]]));return
  st['phone']=ph;st['step']='gov_dob';send(chat,text(uid,'dob'),buttons([[('0',CANCEL)]]));return
 if step=='gov_dob':
  if not re.fullmatch(r'1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])',t):send(chat,text(uid,'dob'),buttons([[('0',CANCEL)]]));return
  st['dob']=t;a=amount('government',500000);rid,code=create(uid,'government',a)
  for k,v in st.get('gov',{}).items():db.answer(rid,k,file_id=v if k in {'id','sim'} else '',answer=v if k not in {'id','sim'} else '')
  db.answer(rid,'fida',st.get('fida',''));db.answer(rid,'yekta',st.get('yekta',''));db.answer(rid,'phone',st['phone']);db.answer(rid,'dob',t);admin_notify(code,'government',a);invoice(uid,chat,rid,code,a,main_menu(lang));return
 if step=='partner_gov_fida':st['fida']=t;st['step']='partner_gov_yekta';send(chat,'🔢 شناسه یکتای مشتری را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='partner_gov_yekta':st['yekta']=t;st['step']='partner_gov_id';send(chat,'🪪 تصویر مدرک شناسایی مشتری را ارسال کنید.',buttons([[('0',CANCEL)]]));return
 if step=='partner_gov_phone':
  ph=re.sub(r'\D','',t)
  if not re.fullmatch(r'09\d{9}',ph):send(chat,'📱 شماره موبایل مشتری را صحیح وارد کنید.',buttons([[('0',CANCEL)]]));return
  st['phone']=ph;st['step']='partner_gov_dob';send(chat,text(uid,'dob'),buttons([[('0',CANCEL)]]));return
 if step=='partner_gov_dob':
  if not re.fullmatch(r'1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])',t):send(chat,text(uid,'dob'),buttons([[('0',CANCEL)]]));return
  a=amount('government',500000);p=db.conn.execute('SELECT * FROM partners WHERE id=?',(st.get('partner_id'),)).fetchone()
  if not p or int(p['balance'])<a:send(chat,f'❌ اعتبار کافی نیست. هزینه {a:,} تومان است.',partner_menu(lang));st['step']='partner_menu';return
  rid,code=db.create_request(db.user('rubika',uid,'',''),'government','rubika',a);db.answer(rid,'partner_id',str(p['id']));db.answer(rid,'fida',st.get('fida',''));db.answer(rid,'yekta',st.get('yekta',''));db.answer(rid,'phone',st['phone']);db.answer(rid,'dob',t)
  db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(a,now(),p['id']));db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_wallet',updated_at=? WHERE id=?",(now(),rid));db.conn.commit();admin_notify(code,'government-partner',a);send(chat,f'✅ خدمت ثبت شد.\n🎫 کد پیگیری: {code}\n💰 کسر از اعتبار: {a:,} تومان\n💰 موجودی: {int(p["balance"])-a:,} تومان',partner_menu(lang));st['step']='partner_menu';return
 if step=='print_color':
  if t.startswith('1') or 'سیاه' in t:st['color']='bw'
  elif t.startswith('2') or 'رنگی' in t:st['color']='color'
  else:send(chat,'🖨 نوع چاپ را انتخاب کنید.',buttons([[('1','⚫ سیاه و سفید'),('2','🌈 رنگی')],[('0',CANCEL)]]));return
  st['step']='print_side';send(chat,'📄 یک‌رو یا پشت‌ورو؟',buttons([[('1','📄 یک‌رو'),('2','🔄 پشت‌ورو')],[('0',CANCEL)]]));return
 if step=='print_side':
  if t.startswith('1'):st['side']='single'
  elif t.startswith('2'):st['side']='double'
  else:return send(chat,'📄 یک‌رو یا پشت‌ورو؟',buttons([[('1','📄 یک‌رو'),('2','🔄 پشت‌ورو')],[('0',CANCEL)]]))
  st['step']='print_copies';send(chat,'🔢 تعداد نسخه از هر صفحه را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='print_copies':
  if not t.isdigit() or int(t)<1:return send(chat,'🔢 تعداد را به صورت عدد مثبت وارد کنید.',buttons([[('0',CANCEL)]]))
  st['copies']=int(t);st['files']=[];st['step']='print_files';send(chat,'📎 فایل‌ها/عکس‌ها را یکی‌یکی بفرستید. بعد «تأیید» را بزنید.',buttons([[('1',OK)],[('0',CANCEL)]]));return
 if step=='print_files' and t in {'1',OK,'تأیید','تایید'}:
  if not st.get('files'):return send(chat,'❌ حداقل یک فایل بفرستید.',buttons([[('0',CANCEL)]]))
  key='print_color' if st['color']=='color' else 'print_bw';a=len(st['files'])*amount(key,0)*st['copies'];rid,code=create(uid,'print',a)
  for i,f in enumerate(st['files']):db.answer(rid,f'file_{i+1}',file_id=f)
  db.answer(rid,'color',st['color']);db.answer(rid,'side',st['side']);db.answer(rid,'copies',str(st['copies']));admin_notify(code,'print',a);invoice(uid,chat,rid,code,a,main_menu(lang));return
 if step=='payment' and t in {'پرداخت کردم','1','تأیید'}:send(chat,'📸 لطفاً رسید پرداخت را به صورت عکس یا فایل ارسال کنید.',buttons([[('0',CANCEL)] ]));st['step']='payment_receipt';return
 if step=='admin_done':finish_request(uid,chat);return
 send(chat,text(uid,'bad'),main_menu(lang))
def process_media(uid,chat,m):
 st=new(uid);fid=media_id(m);step=st.get('step')
 if not fid:return send(chat,'❌ فایل یا تصویر معتبر دریافت نشد.')
 if step=='fida_doc':st['doc']=fid;st['step']='fida_phone';send(chat,'📱 شماره موبایل مشترک را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='gov_id':st.setdefault('gov',{})['id']=fid;st['step']='gov_sim';send(chat,'📄 تصویر سند سیم‌کارت مشترک را بفرستید؛ اگر ندارید «ندارم» بنویسید.',buttons([[('0',CANCEL)]]));return
 if step=='gov_sim':st.setdefault('gov',{})['sim']=fid;st['step']='gov_phone';send(chat,text(uid,'phone'),buttons([[('0',CANCEL)]]));return
 if step=='partner_gov_id':st.setdefault('gov',{})['id']=fid;st['step']='partner_gov_sim';send(chat,'📄 سند سیم‌کارت مشتری را ارسال کنید؛ اگر ندارد «ندارم» بنویسید.',buttons([[('0',CANCEL)]]));return
 if step=='partner_gov_sim':st.setdefault('gov',{})['sim']=fid;st['step']='partner_gov_phone';send(chat,'📱 شماره موبایل مشتری را وارد کنید.',buttons([[('0',CANCEL)]]));return
 if step=='topup_receipt':tid=db.add_topup(st['partner_id'],int(st['topup_amount']),fid);st['step']='partner_menu';send(chat,f'✅ رسید شارژ #{tid} ثبت شد و منتظر تأیید مدیر است.',partner_menu(st.get('lang','fa')));admin_notify(f'TOPUP-{tid}','topup',int(st['topup_amount']));return
 if step=='print_files':st.setdefault('files',[]).append(fid);send(chat,f'✅ فایل شماره {len(st["files"])} دریافت شد. فایل بعدی را بفرستید یا «تأیید» را بزنید.',buttons([[('1',OK)],[('0',CANCEL)]]));return
 if step=='payment_receipt':
  rid=st.get('request_id');db.conn.execute("UPDATE requests SET payment_status='pending',status='payment_review',payment_note=?,updated_at=? WHERE id=?",(fid,now(),rid));db.conn.commit();send(chat,f'✅ رسید دریافت شد.\n🎫 کد پیگیری: {st.get("code") }\nمنتظر بررسی مدیر باشید.',main_menu(st.get('lang','fa')));st['step']='menu';return
 send(chat,text(uid,'bad'),main_menu(st.get('lang','fa')))
def process(u):
 if not isinstance(u,dict):return
 m=msg_payload(u);chat=str(u.get('chat_id') or m.get('chat_id') or '');
 if not chat:return
 uid=chat
 if u.get('type')=='StartedBot':S[uid]={'lang':'fa','step':'language'};send(chat,TEXT['fa']['lang'],lang_menu());return
 t=msg_text(m)
 if t=='/start':S[uid]={'lang':'fa','step':'language'};send(chat,TEXT['fa']['lang'],lang_menu());return
 if t and t in {CANCEL,'انصراف','لغو','Cancel','cancel','إلغاء'}:cancel(uid,chat);return
 if media_id(m):process_media(uid,chat,m);return
 process_text(uid,chat,t)
def run():
 me=call('getMe');log.info('Rubika getMe OK: %s',me);offset=None;log.info('NetYar Rubika robust polling started')
 while True:
  try:
   p={'limit':20}
   if offset:p['offset_id']=offset
   d=call('getUpdates',p);updates=d if isinstance(d,list) else (d.get('updates',[]) if isinstance(d,dict) else [])
   nxt=d.get('next_offset_id') if isinstance(d,dict) else None
   for u in updates:
    try:process(u)
    except Exception:log.exception('Rubika update failed')
   if nxt:offset=str(nxt)
   time.sleep(.5)
  except Exception:log.exception('Rubika polling error');time.sleep(4)
if __name__=='__main__':run()
