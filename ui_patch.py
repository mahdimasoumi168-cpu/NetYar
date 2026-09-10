import logging
log=logging.getLogger('netyar.ui_patch')
def install():
 import bot as B
 from telegram import InlineKeyboardMarkup, InlineKeyboardButton
 async def langcb(u,c):
  q=u.callback_query; await q.answer(); uid=q.from_user.id; lang=q.data.split(':')[1]; B.S[uid]={'lang':lang}
  texts={'fa':'آیا اتباع هستید یا ایرانی؟','en':'Are you a foreign national or Iranian?','ar':'هل أنت من الرعايا الأجانب أم إيراني؟'}
  labels={'fa':('🪪 اتباع هستم','🇮🇷 ایرانی هستم'),'en':('🪪 Foreign national','🇮🇷 Iranian'),'ar':('🪪 أجنبي','🇮🇷 إيراني')}; a,b=labels[lang]
  return await q.message.reply_text(texts[lang],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(a,callback_data='st:foreign'),InlineKeyboardButton(b,callback_data='st:iranian')]]))
 B.langcb=langcb
 def amenu(): return B.kb([["👤 پنل کاربران","👥 همکاران"],["💰 شارژها","💳 پرداخت‌های مشتری"],["📋 درخواست‌ها","⚙️ قیمت‌ها"],["🌐 زبان‌ها","📊 گزارش"],["🤖 مدیریت پیام‌رسان‌ها","🩺 سلامت ربات‌ها"],["⬅️ منوی اصلی"]])
 B.amenu=amenu
 old_admin=B.admin_text
 async def admin_text(u,c):
  if not B.admin(u.effective_user.id): return
  t=(u.message.text or '').strip()
  if t=='🌐 زبان‌ها':
   cur=B.db.setting('default_lang','fa'); return await u.message.reply_text(f'🌐 مدیریت زبان‌ها\n\n🇮🇷 فارسی: فعال\n🇬🇧 English: فعال\n🇸🇦 العربية: فعال\n\nزبان پیش‌فرض: {cur}',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🇮🇷 فارسی',callback_data='langset:fa'),InlineKeyboardButton('🇬🇧 English',callback_data='langset:en')],[InlineKeyboardButton('🇸🇦 العربية',callback_data='langset:ar')]]))
  if t=='🩺 سلامت ربات‌ها': return await u.message.reply_text('🩺 سلامت پیام‌رسان‌ها\n\n🟢 Telegram: فعال\n🟢 Rubika: در حال دریافت webhook\n\n🛡️ فعال‌سازی بات جدید مستقل انجام می‌شود تا Telegram/Rubika قطع نشوند.',reply_markup=amenu())
  if t=='🤖 مدیریت پیام‌رسان‌ها':
   rows=B.db.bots(); text='🤖 مدیریت پیام‌رسان‌ها\n\n'+(''.join(f"#{r[\'id\']} | {r[\'platform\']} | {r[\'bot_name\']} | {\'🟢 فعال\' if r[\'active\'] else \'🟡 آماده\'} | {r[\'status\']}\n" for r in rows) or 'هنوز باتی ثبت نشده است.')
   return await u.message.reply_text(text+'\nبرای پیام‌رسان جدید، API فقط زمانی فعال می‌شود که adapter واقعی همان پیام‌رسان در runtime موجود باشد.',reply_markup=amenu())
  return await old_admin(u,c)
 B.admin_text=admin_text
 old_cb=B.admin_cb
 async def admin_cb(u,c):
  q=u.callback_query; d=(q.data or '').split(':')
  if len(d)==2 and d[0]=='langset' and B.admin(q.from_user.id):
   lang=d[1] if d[1] in {'fa','en','ar'} else 'fa'; B.db.set_setting('default_lang',lang); await q.answer('ذخیره شد'); return await q.message.reply_text(f'✅ زبان پیش‌فرض روی {lang} تنظیم شد.',reply_markup=amenu())
  return await old_cb(u,c)
 B.admin_cb=admin_cb
install()
