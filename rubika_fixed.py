import os,time,re,logging,requests
from core import db,check_password,now
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s'); log=logging.getLogger('rubika')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip(); BASE=f'https://botapi.rubika.ir/v3/{TOKEN}'
if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
S={}; CANCEL='❌ انصراف'; OK='✅ تأیید'; ADM={x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}; ACMD=os.getenv('ADMIN_COMMAND','/Admin2025')
T={'fa':{'lang':'🌐 زبان را انتخاب کنید:','cit':'آیا اتباع هستید یا ایرانی؟','iran':'🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.','menu':'سلام 👋\nبه بات «کمک یار مهاجر» خوش آمدید.\nخدمت موردنظر را انتخاب کنید:','phone':'📱 شماره موبایل مشترک را وارد کنید.','pass':'🔐 رمز عبور همکار را وارد کنید.','bad':'❌ اطلاعات واردشده صحیح نیست.','bal':'💰 موجودی: {n:,} تومان','track':'🎫 کد پیگیری را وارد کنید.','id':'🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.','fida':'🆔 فیدا/اختصاصی مشترک را وارد کنید.','yekta':'🔢 یکتای مشترک را وارد کنید.','dob':'🎂 تاریخ تولد مشترک را مثل 1356/01/01 وارد کنید.','govphone':'📱 شماره موبایل مشترک را وارد کنید.','print':'🖨 سیاه‌وسفید یا رنگی؟','side':'📄 یک‌رو یا پشت‌ورو؟','copies':'🔢 تعداد نسخه از هر صفحه را وارد کنید.','files':'📎 فایل‌ها/عکس‌ها را بفرستید؛ پایان: تأیید.','admin':'🛠 پنل مدیریت پیشرفته','saved':'✅ ذخیره شد.','no':'❌ موردی پیدا نشد.'},'en':{'lang':'🌐 Choose language:','cit':'Foreign national or Iranian?','iran':'🇮🇷 Services are currently unavailable for Iranian users.','menu':'Hello 👋\nWelcome to Mohajer Helper.\nChoose a service:','phone':'📱 Enter customer mobile.','pass':'🔐 Enter partner password.','bad':'❌ Invalid information.','bal':'💰 Balance: {n:,} toman','track':'🎫 Enter tracking code.','id':'🪪 Send customer ID document.','fida':'🆔 Enter customer FIDA/special ID.','yekta':'🔢 Enter customer unique ID.','dob':'🎂 Enter birth date like 1356/01/01.','govphone':'📱 Enter customer mobile.','print':'🖨 Black/white or color?','side':'📄 One-sided or two-sided?','copies':'🔢 Enter copies per page.','files':'📎 Send files/images; Confirm when finished.','admin':'🛠 Advanced admin panel','saved':'✅ Saved.','no':'❌ Not found.'},'ar':{'lang':'🌐 اختر اللغة:','cit':'هل أنت أجنبي أم إيراني؟','iran':'🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين.','menu':'مرحباً 👋\nأهلاً بكم في مساعد المهاجر.\nاختر الخدمة:','phone':'📱 أدخل رقم هاتف العميل.','pass':'🔐 أدخل كلمة مرور الشريك.','bad':'❌ المعلومات غير صحيحة.','bal':'💰 الرصيد: {n:,} تومان','track':'🎫 أدخل رمز المتابعة.','id':'🪪 أرسل وثيقة هوية العميل.','fida':'🆔 أدخل رقم فيدا.','yekta':'🔢 أدخل المعرف الفريد.','dob':'🎂 أدخل تاريخ الميلاد مثل 1356/01/01.','govphone':'📱 أدخل هاتف العميل.','print':'🖨 أبيض وأسود أم ملون؟','side':'📄 أحادي أم مزدوج؟','copies':'🔢 أدخل عدد النسخ.','files':'📎 أرسل الملفات ثم تأكيد.','admin':'🛠 لوحة الإدارة المتقدمة','saved':'✅ تم الحفظ.','no':'❌ غير موجود.'}}
def api(m,p=None):
 r=requests.post(f'{BASE}/{m}',json=p or {},timeout=30);r.raise_for_status();b=r.json();return b.get('data',b) if isinstance(b,dict) else b
def btn(*rs):return [[{'id':str(i),'type':'Simple','button_text':t} for i,t in r] for r in rs]
def send(c,text,rs=None):
 p={'chat_id':str(c),'text':text}
 if rs:p.update(chat_keypad_type='New',chat_keypad={'rows':btn(*rs),'resize_keyboard':True,'one_time_keyboard':False})
 for i in range(3):
  try:return api('sendMessage',p)
  except requests.RequestException:
   if i==2:raise
   time.sleep(i+1)
def lang(u):return S.get(str(u),{}).get('lang','fa')
def tr(u,k,**kw):return T[lang(u)][k].format(**kw)
def menus(l):
 if l=='en':return [('1','🪪 FIDA'),('2','🖨 Print')],[('3','🏛 Government'),('4','🎫 Tracking')],[('5','📱 SIM'),('6','📝 Screening')],[('7','💰 Wallet'),('8','👥 Partner panel')],[('0',CANCEL)]
 if l=='ar':return [('1','🪪 فيدا'),('2','🖨 طباعة')],[('3','🏛 الحكومة'),('4','🎫 متابعة')],[('5','📱 شريحة'),('6','📝 فحص')],[('7','💰 محفظتي'),('8','👥 الشركاء')],[('0','❌ إلغاء')]
 return [('1','🪪 فیدای غیر حضوری'),('2','🖨 خدمات چاپ')],[('3','🏛 حل مشکل دولت من'),('4','🎫 پیگیری')],[('5','📱 خدمات سیم کارت'),('6','📝 آزمون غربالگری و پیگیری')],[('7','💰 کیف پول من'),('8','👥 پنل همکاران')],[('0',CANCEL)]
def mainkb(l):return menus(l)
def notify(text):
 for a in ADM:
  try:send(a,text)
  except:pass
def newreq(uid,key,amount):
 u=db.user('rubika',str(uid));return db.create_request(u,key,'rubika',int(amount))
def cancel(u,c):
 p=S.get(str(u),{}).get('partner_id');S[str(u)]={'lang':lang(u),'step':'menu','partner_id':p};send(c,'عملیات لغو شد. به منوی اصلی برگشتید. ✅',mainkb(lang(u)))
def txt(m):
 if not isinstance(m,dict):return ''
 if m.get('text'):return str(m['text']).strip()
 a=m.get('aux_data') or {};return str(a.get('button_id') or a.get('text') or '').strip() if isinstance(a,dict) else ''
def fid(m):
 f=m.get('file') if isinstance(m,dict) else None;return f.get('file_id') if isinstance(f,dict) else ''
def handle(u,c,x,m):
 u=str(u);s=S.setdefault(u,{'lang':'fa','step':'language'});st=s['step'];l=lang(u)
 if x in {CANCEL,'0','انصراف','لغو','Cancel','cancel','إلغاء'}:return cancel(u,c)
 if x==ACMD:
  if u not in ADM:return send(c,'⛔ دسترسی مدیریت ندارید.')
  s['admin']=1;s['step']='admin';return send(c,tr(u,'admin')+'\nگزینه را انتخاب کنید:',admin_kb())
 if st=='language':
  z={'1':'fa','2':'en','3':'ar','فارسی':'fa','🇮🇷 فارسی':'fa','English':'en','🇬🇧 English':'en','العربية':'ar','🇸🇦 العربية':'ar'}.get(x)
  if not z:return send(c,T['fa']['lang'],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
  s['lang']=z;s['step']='cit';return send(c,T[z]['cit'],[[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')]])
 if st=='cit':
  if x=='1':s['step']='menu';return send(c,tr(u,'menu'),mainkb(l))
  if x=='2':s['step']='iran';return send(c,tr(u,'iran'),[[('1','👥 پنل همکاران'),('2','🎫 پیگیری')]])
 if st=='iran':
  if x=='1':s['step']='pp';return send(c,tr(u,'phone'),[[('0',CANCEL)]])
  if x=='2':s['step']='track';return send(c,tr(u,'track'),[[('0',CANCEL)]])
 if st=='menu':
  if x.startswith('1'):s['step']='fidaid';return send(c,tr(u,'id'),[[('0',CANCEL)]])
  if x.startswith('2'):s['step']='pc';return send(c,tr(u,'print'),[[('1','⚫ سیاه‌وسفید'),('2','🌈 رنگی')],[('0',CANCEL)]])
  if x.startswith('3'):s['step']='gf';return send(c,tr(u,'fida'),[[('0',CANCEL)]])
  if x.startswith('4'):s['step']='track';return send(c,tr(u,'track'),[[('0',CANCEL)]])
  if x.startswith('7'):
   r=db.conn.execute('SELECT balance FROM partners WHERE id=?',(s.get('partner_id'),)).fetchone() if s.get('partner_id') else None;return send(c,tr(u,'bal',n=int(r['balance']) if r else 0),mainkb(l))
  if x.startswith('8'):s['step']='pp';return send(c,tr(u,'phone'),[[('0',CANCEL)]])
  return send(c,tr(u,'menu'),mainkb(l))
 if st=='pp':
  p=db.partner(x)
  if not p:return send(c,tr(u,'bad'))
  s['phone']=x;s['step']='pw';return send(c,tr(u,'pass'),[[('0',CANCEL)]])
 if st=='pw':
  p=db.partner(s.get('phone',''))
  if not p or not check_password(x,p['password_hash']):return send(c,tr(u,'bad'))
  s['partner_id']=p['id'];s['step']='pm';return send(c,'👥 پنل همکاران\n'+tr(u,'bal',n=int(p['balance'])),partner_kb())
 if st=='pm':
  if x=='1':s['step']='ta';return send(c,'💰 مبلغ شارژ را به تومان وارد کنید.')
  if x=='2':s['step']='track';return send(c,tr(u,'track'))
  if x=='4':
   r=db.conn.execute('SELECT balance FROM partners WHERE id=?',(s['partner_id'],)).fetchone();return send(c,tr(u,'bal',n=int(r['balance'])),partner_kb())
  if x=='3':
   rs=db.conn.execute('SELECT tracking_code,service_key,status,amount FROM requests ORDER BY id DESC LIMIT 20').fetchall();return send(c,'\n'.join(f"🎫 {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,}" for r in rs) or tr(u,'no'),partner_kb())
  return send(c,'👥 پنل همکاران',partner_kb())
 if st=='ta':
  if not x.isdigit() or int(x)<=0:return send(c,'💰 مبلغ شارژ را به تومان وارد کنید.')
  s['ta']=int(x);s['step']='tr';return send(c,'📸 رسید واریز را ارسال کنید.')
 if st=='tr':
  f=fid(m)
  if not f:return send(c,'📸 رسید واریز را ارسال کنید.')
  tid=db.add_topup(s['partner_id'],s['ta'],f);notify(f'💰 شارژ جدید همکار #{tid}\nشماره: {s.get("phone")}\nمبلغ: {s["ta"]:,} تومان');s['step']='pm';return send(c,f'✅ رسید شارژ #{tid} ثبت شد و منتظر تأیید مدیر است.',partner_kb())
 if st=='track':
  r=db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(x,)).fetchone();return send(c,(f"🎫 {r['tracking_code']}\n📌 وضعیت: {r['status']}\n💳 پرداخت: {r['payment_status']}\n💰 مبلغ: {int(r['amount']):,} تومان" if r else tr(u,'no')),mainkb(l))
 if st=='fidaid':
  if not fid(m):return send(c,tr(u,'id'))
  s['step']='fidaph';s['fidaid']=fid(m);return send(c,tr(u,'phone'))
 if st=='fidaph':
  amount=int(db.setting('price_fida','0') or 0);_,code=newreq(u,'fida',amount);notify(f'🪪 فیدا جدید\n🎫 {code}\nکاربر: {u}\nموبایل مشترک: {x}');s['step']='menu';return send(c,f'✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}',mainkb(l))
 if st=='pc':s['color']='bw' if x=='1' else 'color';s['step']='ps';return send(c,tr(u,'side'),[[('1','📄 یک‌رو'),('2','📑 پشت‌ورو')],[('0',CANCEL)]])
 if st=='ps':s['side']='single' if x=='1' else 'duplex';s['step']='copies';return send(c,tr(u,'copies'))
 if st=='copies':
  if not x.isdigit() or int(x)<1:return send(c,tr(u,'copies'))
  s['copies']=int(x);s['step']='files';s['files']=[];return send(c,tr(u,'files'),[[('1',OK),('0',CANCEL)]])
 if st=='files':
  if fid(m):s['files'].append(fid(m));return send(c,'✅ دریافت شد. مورد بعدی را بفرستید یا تأیید را بزنید.',[[('1',OK),('0',CANCEL)]])
  if x==OK and s['files']:
   key='price_print_color' if s['color']=='color' else 'price_print_bw';amount=int(db.setting(key,'0') or 0)*s['copies'];_,code=newreq(u,'print',amount);notify(f'🖨 چاپ جدید\n🎫 {code}\nکاربر: {u}\nفایل: {len(s["files"])}\nمبلغ: {amount:,} تومان');s['step']='menu';return send(c,f'✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}',mainkb(l))
  return send(c,tr(u,'files'),[[('1',OK),('0',CANCEL)]])
 if st=='gf':s['gf']=x;s['step']='gy';return send(c,tr(u,'yekta'))
 if st=='gy':s['gy']=x;s['step']='dob';return send(c,tr(u,'dob'))
 if st=='dob':
  if not re.fullmatch(r'\d{4}/\d{2}/\d{2}',x):return send(c,tr(u,'dob'))
  s['dob']=x;s['step']='gid';return send(c,tr(u,'id'))
 if st=='gid':
  if not fid(m):return send(c,tr(u,'id'))
  s['gid']=fid(m);s['step']='gp';return send(c,tr(u,'govphone'))
 if st=='gp':
  amount=int(db.setting('price_government','500000') or 500000);_,code=newreq(u,'government',amount);notify(f'🏛 دولت من جدید\n🎫 {code}\nکاربر: {u}\nفیدا: {s.get("gf")}\nیکتا: {s.get("gy")}\nتولد: {s.get("dob")}\nموبایل: {x}\nمبلغ: {amount:,} تومان');s['step']='menu';return send(c,f'✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان',mainkb(l))
 if st.startswith('admin'):return admin(u,c,x)
 return send(c,tr(u,'menu'),mainkb(l))
def partner_kb():return [[{'id':'1','type':'Simple','button_text':'➕ شارژ حساب'},{'id':'2','type':'Simple','button_text':'🔎 پیگیری کد'}],[{'id':'3','type':'Simple','button_text':'📋 سوابق'},{'id':'4','type':'Simple','button_text':'💰 موجودی'}],[{'id':'0','type':'Simple','button_text':CANCEL}]]
def admin_kb():return [[{'id':'1','type':'Simple','button_text':'👥 همکاران'},{'id':'2','type':'Simple','button_text':'➕ افزودن همکار'}],[{'id':'3','type':'Simple','button_text':'💰 شارژها'},{'id':'4','type':'Simple','button_text':'📋 درخواست‌ها'}],[{'id':'5','type':'Simple','button_text':'💳 پرداخت‌ها'},{'id':'6','type':'Simple','button_text':'⚙️ قیمت‌ها'}],[{'id':'7','type':'Simple','button_text':'🤖 افزودن بات'},{'id':'8','type':'Simple','button_text':'🤖 بات‌ها'}],[{'id':'9','type':'Simple','button_text':'📊 گزارش'},{'id':'0','type':'Simple','button_text':CANCEL}]]
def admin(u,c,x):
 if u not in ADM:return send(c,'⛔ دسترسی مدیریت ندارید.')
 s=S[u];st=s['step']
 if st=='admin':
  if x=='1':
   r=db.conn.execute('SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC').fetchall();return send(c,'\n'.join(f"#{a['id']} | {a['name']} | {a['phone']} | {int(a['balance']):,} | {a['active']}" for a in r) or tr(u,'no'),admin_kb())
  if x=='2':s['step']='admin_pp';return send(c,'📱 شماره همراه همکار جدید را وارد کنید.')
  if x=='3':r=db.conn.execute("SELECT t.id,p.phone,t.amount FROM topups t JOIN partners p ON p.id=t.partner_id WHERE t.status='pending' ORDER BY t.id DESC").fetchall();return send(c,'\n'.join(f"#{a['id']} | {a['phone']} | {int(a['amount']):,}" for a in r) or tr(u,'no'),admin_kb())
  if x=='4':r=db.conn.execute('SELECT tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 30').fetchall();s['step']='admin_sc';return send(c,'\n'.join(f"{a['tracking_code']} | {a['service_key']} | {a['status']} | {int(a['amount']):,} | {a['payment_status']}" for a in r) or tr(u,'no'),[[('1','🔄 تغییر وضعیت'),('0',CANCEL)]])
  if x=='5':r=db.conn.execute("SELECT tracking_code,amount,payment_status FROM requests WHERE payment_status='pending'").fetchall();return send(c,'\n'.join(f"{a['tracking_code']} | {int(a['amount']):,} | {a['payment_status']}" for a in r) or tr(u,'no'),admin_kb())
  if x=='6':s['step']='admin_price';return send(c,'⚙️ کلید خدمت و مبلغ؛ مثال: government 500000')
  if x=='7':s['step']='admin_platform';return send(c,'🤖 پیام‌رسان را وارد کنید: rubika / eitaa / bale')
  if x=='8':r=db.bots();return send(c,'\n'.join(f"#{a['id']} | {a['platform']} | {a['bot_name']} | {'فعال' if a['active'] else 'غیرفعال'} | {a['status']}" for a in r) or tr(u,'no'),admin_kb())
  if x=='9':p=db.conn.execute('SELECT COUNT(*) n FROM partners').fetchone()['n'];q=db.conn.execute('SELECT COUNT(*) n FROM requests').fetchone()['n'];t=db.conn.execute("SELECT COUNT(*) n FROM topups WHERE status='pending'").fetchone()['n'];return send(c,f'📊 گزارش\nهمکاران: {p}\nدرخواست‌ها: {q}\nشارژهای معلق: {t}',admin_kb())
  return send(c,tr(u,'admin'),admin_kb())
 if st=='admin_pp':s['newp']=x;s['step']='admin_pn';return send(c,'👤 نام همکار را وارد کنید.')
 if st=='admin_pn':s['newn']=x;s['step']='admin_pw';return send(c,'🔐 رمز عبور همکار را وارد کنید.')
 if st=='admin_pw':
  try:db.add_partner(s['newp'],x,s['newn']);s['step']='admin';return send(c,'✅ همکار اضافه شد.',admin_kb())
  except:return send(c,'❌ این شماره قبلاً ثبت شده است.',admin_kb())
 if st=='admin_price':
  a=x.split();
  if len(a)==2 and a[1].isdigit():db.set_setting('price_'+a[0],int(a[1]));db.conn.execute('UPDATE services SET price=? WHERE key=?',(int(a[1]),a[0]));db.conn.commit();s['step']='admin';return send(c,tr(u,'saved'),admin_kb())
  return send(c,'⚠️ قالب نادرست است.')
 if st=='admin_platform':s['platform']=x.lower();s['step']='admin_token';return send(c,'🔑 API Token را ارسال کنید.')
 if st=='admin_token':s['token']=x;s['step']='admin_bn';return send(c,'🤖 نام بات را وارد کنید.')
 if st=='admin_bn':
  try:db.add_bot(s['platform'],x,s['token']);s['step']='admin';return send(c,'✅ بات ثبت شد. برای اجرای واقعی ایتا/بله Adapter همان پیام‌رسان باید فعال باشد؛ روبیکا همین Worker را دارد. توکن در پیام/لاگ نمایش داده نمی‌شود.',admin_kb())
  except Exception as e:return send(c,f'❌ خطا: {e}',admin_kb())
 if st=='admin_sc':
  if x!='1':s['step']='admin';return send(c,tr(u,'admin'),admin_kb())
  s['step']='admin_code';return send(c,'🎫 کد پیگیری را وارد کنید.')
 if st=='admin_code':
  r=db.conn.execute('SELECT id,user_id,tracking_code FROM requests WHERE tracking_code=?',(x,)).fetchone()
  if not r:s['step']='admin';return send(c,'❌ کد پیدا نشد.',admin_kb())
  s['rid']=r['id'];s['rcode']=r['tracking_code'];s['ruid']=db.conn.execute('SELECT external_id FROM users WHERE id=?',(r['user_id'],)).fetchone()['external_id'];s['step']='admin_status';return send(c,'📌 وضعیت جدید را بنویسید: درحال بررسی / انجام شد / نیاز به اصلاح / لغو شد')
 if st=='admin_status':
  db.conn.execute('UPDATE requests SET status=?,updated_at=? WHERE id=?',(x,now(),s['rid']));db.conn.commit();send(s['ruid'],f'🔔 بروزرسانی خدمت\n🎫 کد پیگیری: {s.get("rcode")}\n📌 وضعیت: {x}');s['step']='admin';return send(c,'✅ وضعیت ثبت شد و پیام خودکار ارسال شد.',admin_kb())
def process(u):
 if not isinstance(u,dict):return
 m=u.get('new_message') or u.get('updated_message') or {};c=u.get('chat_id') or m.get('chat_id');sid=m.get('sender_id') or c
 if not c or not sid:return
 x=txt(m)
 if x=='/start':S[str(sid)]={'lang':'fa','step':'language'};return send(c,T['fa']['lang'],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
 db.user('rubika',str(sid),full_name=str(sid));handle(sid,c,x,m)
def main():
 log.info('Rubika getMe=%s',api('getMe'));off=None
 while True:
  try:
   p={'limit':50};
   if off:p['offset_id']=off
   d=api('getUpdates',p);us=d.get('updates',[]) if isinstance(d,dict) else [];nxt=d.get('next_offset_id') if isinstance(d,dict) else None
   for u in us:
    try:process(u)
    except Exception:log.exception('update failed')
   if nxt:off=str(nxt)
   time.sleep(.4)
  except Exception as e:log.warning('poll error: %s',e);time.sleep(3)
if __name__=='__main__':main()
