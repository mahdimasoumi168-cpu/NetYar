"""Final Telegram UI consistency layer."""
import logging
log=logging.getLogger('netyar.ui_patch')

def install():
 import bot as B
 if getattr(B,'_netyar_ui_patch_installed',False): return
 def citizen_rows(lang):
  if lang=='en': return [["🪪 Foreign national","🇮🇷 Iranian"],["❌ Cancel"]]
  if lang=='ar': return [["🪪 أجنبي","🇮🇷 إيراني"],["❌ إلغاء"]]
  return [["🪪 اتباع هستم","🇮🇷 ایرانی هستم"],[B.CANCEL]]
 async def start(u,c):
  uid=u.effective_user.id; B.db.user('telegram',uid,u.effective_user.username,u.effective_user.full_name); B.S[uid]={}
  return await u.message.reply_text('سلام و خوش آمدید 🌷\n\nزبان موردنظر را انتخاب کنید:',reply_markup=B.kb([["🇮🇷 فارسی","🇬🇧 English","🇸🇦 العربية"]]))
 async def langcb(u,c):
  q=u.callback_query; await q.answer(); uid=q.from_user.id; lang=(q.data or '').split(':',1)[-1]
  if lang not in {'fa','en','ar'}: lang='fa'
  old=B.S.get(uid,{}); B.S[uid]={k:old[k] for k in ('partner_id','partner_active','admin') if k in old}; B.S[uid]['lang']=lang
  text={'fa':'آیا اتباع هستید یا ایرانی؟','en':'Are you a foreign national or Iranian?','ar':'هل أنت أجنبي أم إيراني؟'}[lang]
  return await q.message.reply_text(text,reply_markup=B.kb(citizen_rows(lang)))
 async def statuscb(u,c):
  q=u.callback_query; await q.answer(); uid=q.from_user.id; status=(q.data or '').split(':',1)[-1]; st=B.S.setdefault(uid,{}); st['status']=status; lang=st.get('lang','fa')
  msg={'fa':'منوی خدمات کمک یار مهاجر 👇','en':'Mohajer Helper services 👇','ar':'قائمة خدمات المهاجرين 👇'}[lang] if status=='foreign' else {'fa':'🇮🇷 خدمات ایرانی فعلاً فعال نیست.','en':'🇮🇷 Services for Iranian users are currently unavailable.','ar':'🇮🇷 الخدمات للمستخدمين الإيرانيين غير متاحة حالياً.'}[lang]
  return await q.message.reply_text(msg,reply_markup=B.main(uid))
 B.start=start; B.langcb=langcb; B.statuscb=statuscb
 def amenu(): return B.kb([["👤 پنل کاربران","👥 همکاران"],["➕ افزودن همکار","💰 شارژها"],["📋 درخواست‌ها","💳 پرداخت‌های مشتری"],["⚙️ قیمت‌ها","📊 گزارش"],["🤖 افزودن بات","🤖 بات‌های متصل"],["🌐 زبان‌ها","🩺 سلامت ربات‌ها"],["⚙️ تنظیمات","📣 اعلان خدمت"],["⬅️ منوی اصلی"]])
 B.amenu=amenu
 old_admin=B.admin_text
 async def admin_text(u,c):
  if not B.admin(u.effective_user.id): return
  t=(u.message.text or '').strip()
  if t=='🌐 زبان‌ها':
   cur=B.db.setting('default_lang','fa'); return await u.message.reply_text(f'🌐 مدیریت زبان‌ها\n\n🇮🇷 فارسی: فعال\n🇬🇧 English: فعال\n🇸🇦 العربية: فعال\n\nزبان پیش‌فرض: {cur}',reply_markup=amenu())
  if t=='🩺 سلامت ربات‌ها': return await u.message.reply_text('🩺 سلامت پیام‌رسان‌ها\n\nTelegram و Rubika از runtime اصلی بررسی می‌شوند.\nBale/Eitaa فقط وقتی adapter واقعی داشته باشند قابل اجرای واقعی هستند.',reply_markup=amenu())
  if t=='⚙️ تنظیمات': return await u.message.reply_text('⚙️ تنظیمات سیستم\n\nبرای تغییر قیمت، زبان پیش‌فرض و اتصال پیام‌رسان‌ها از گزینه‌های مربوط در همین پنل استفاده کنید.',reply_markup=amenu())
  return await old_admin(u,c)
 B.admin_text=admin_text
 old_cb=B.admin_cb
 async def admin_cb(u,c):
  q=u.callback_query; d=(q.data or '').split(':')
  if len(d)==2 and d[0]=='langset' and B.admin(q.from_user.id):
   lang=d[1] if d[1] in {'fa','en','ar'} else 'fa'; B.db.set_setting('default_lang',lang); await q.answer('ذخیره شد'); return await q.message.reply_text(f'✅ زبان پیش‌فرض روی {lang} تنظیم شد.',reply_markup=amenu())
  return await old_cb(u,c)
 B.admin_cb=admin_cb; B._netyar_ui_patch_installed=True; log.info('NetYar UI patch installed')
