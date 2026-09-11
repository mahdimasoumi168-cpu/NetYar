"""Rubika side of the durable admin control center."""
import logging
from admin_control_v5 import get, put, set_service, service_rows, ensure
log=logging.getLogger("netyar.rubika_admin_v5")
DONE=False

def install():
 global DONE
 if DONE:return
 ensure()
 try:
  import rubika_v2 as R
  old_rows=getattr(R,"admin_rows",None)
  old_admin=getattr(R,"admin",None)
  def rows():
   base=[[('1','👥 کاربران'),('2','🤝 همکاران')],[('3','📋 درخواست‌ها'),('4','💰 شارژها')],[('5','🟢/🔴 خدمات ایرانی'),('6','🟢/🔴 خدمات اتباع')],[('7','💰 قیمت خدمات'),('8','📝 تغییر متن‌ها')],[('9','🤖 افزودن بات'),('10','👤 مدیران')],[('11','📊 گزارش‌ها'),('12','🎫 تیکت‌ها')],[('13','📎 مدارک و فایل‌ها'),('14','🔄 همگام‌سازی')],[('15','🔄 شروع مجدد')],[('16','📞 پشتیبانی'),('17','⚙️ تنظیمات پایه')],[('0','⬅️ منوی اصلی')]]
   return base
  R.admin_rows=rows
  def admin(uid,chat,x):
   st=R.STATE.setdefault(str(uid),{}); x=str(x).strip()
   if x=='6': st['step']='admin_service_foreign'; R.send(chat,'🇦🇫 خدمات اتباع\nکلید خدمت را ارسال کنید؛ مثال: fida',[[('10','🔄 شروع مجدد')]]); return
   if x=='5': st['step']='admin_service_iranian'; R.send(chat,'🇮🇷 خدمات ایرانی\nکلید خدمت را ارسال کنید.',[[('10','🔄 شروع مجدد')]]); return
   if x in {'16','📞 پشتیبانی'}: st['step']='admin_support'; R.send(chat,f"📞 پشتیبانی فعلی: {get('support_id','@Good_ok_2000')}\nشناسه جدید را ارسال کنید.",[[('10','🔄 شروع مجدد')]]); return
   if x=='17': st['step']='admin_base'; R.send(chat,'⚙️ تنظیمات پایه: support / restart / disabled\nکلید را ارسال کنید.',[[('10','🔄 شروع مجدد')]]); return
   if x=='7': st['step']='admin_price'; R.send(chat,'💰 کلید خدمت را ارسال کنید؛ مثال: government',[[('10','🔄 شروع مجدد')]]); return
   if x=='8': st['step']='admin_text'; R.send(chat,'📝 کلید متن را ارسال کنید: welcome_fa / iranian_text / foreign_text / support_text / restart_text / disabled_text',[[('10','🔄 شروع مجدد')]]); return
   step=st.get('step','')
   if step in {'admin_service_foreign','admin_service_iranian'}:
    r=R.db.conn.execute('SELECT key,name,active FROM services WHERE key=?',(x,)).fetchone()
    if not r: R.send(chat,'❌ کلید خدمت پیدا نشد.'); return
    group='iranian' if step.endswith('iranian') else 'foreign'; set_service(x,not bool(r['active']),group=group); R.send(chat,('🟢 فعال شد: ' if not r['active'] else '🔴 بسته شد: ')+r['name'],rows()); return
   if step=='admin_price':
    r=R.db.conn.execute('SELECT key,name,price FROM services WHERE key=?',(x,)).fetchone()
    if not r:R.send(chat,'❌ خدمت پیدا نشد.');return
    st['price_key']=x;st['step']='admin_price_value';R.send(chat,f"💰 قیمت فعلی {r['name']}: {r['price']:,}\nمبلغ جدید را عددی بفرستید.");return
   if step=='admin_price_value':
    if not x.isdigit():R.send(chat,'❌ فقط عدد وارد کنید.');return
    set_service(st['price_key'],price=int(x));st['step']='admin';R.send(chat,'✅ قیمت ذخیره شد.',rows());return
   if step=='admin_text':
    st['text_key']=x;st['step']='admin_text_value';R.send(chat,f"📝 متن فعلی:\n{get(x,'')}\n\nمتن جدید را ارسال کنید.");return
   if step=='admin_text_value':
    put(st['text_key'],x);st['step']='admin';R.send(chat,'✅ متن ذخیره شد.',rows());return
   if step=='admin_support':
    v=x if x.startswith('@') else '@'+x;put('support_id',v);put('support_text','📞 پشتیبانی: '+v);st['step']='admin';R.send(chat,'✅ پشتیبانی ذخیره شد.',rows());return
   if step=='admin_base':
    if x not in {'support','restart','disabled'}:R.send(chat,'❌ کلید نامعتبر است.');return
    st['base_key']=x;st['step']='admin_base_value';R.send(chat,f"مقدار فعلی: {get(x+'_text',get(x,''))}\nمقدار جدید را ارسال کنید.");return
   if step=='admin_base_value':
    k=st.get('base_key'); put(k+'_text' if k in {'restart','disabled'} else k,x);st['step']='admin';R.send(chat,'✅ تنظیم ذخیره شد.',rows());return
   if old_admin:return old_admin(uid,chat,x)
   R.send(chat,'🛠 پنل مدیریت',rows())
  R.admin=admin
 except Exception:log.exception('rubika admin control v5 failed')
 DONE=True
