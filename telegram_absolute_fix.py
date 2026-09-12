"""Absolute Telegram callback/navigation owner."""
import logging
from types import SimpleNamespace
from telegram import CallbackQueryHandler, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop

log=logging.getLogger("netyar.telegram.absolute_fix")
ALIASES={
 "🔷 👥 پنل همکاران":"👥 پنل همکاران","👥 Partner panel":"👥 پنل همکاران","👥 لوحة الشركاء":"👥 پنل همکاران",
 "🔷 🛠 پنل مدیریت بات":"🛠 پنل مدیریت بات","🛠 Admin panel":"🛠 پنل مدیریت بات","🛠 لوحة الإدارة":"🛠 پنل مدیریت بات",
 "🔷 ➕ شارژ حساب":"➕ شارژ حساب","🔷 🏛 حل مشکل سامانه دولت من":"🏛 حل مشکل سامانه دولت من","🔷 🔎 پیگیری کد":"🔎 پیگیری کد","🔷 📋 سوابق":"📋 سوابق","🔷 💰 موجودی":"💰 موجودی","🔷 🚪 خروج از پنل":"🚪 خروج از پنل",
 "📨 ارسال پیام به مدیریت":"✉️ تیکت به مدیریت","✉️ ارسال تیکت به مدیریت":"✉️ تیکت به مدیریت","📝 تیکت به مدیریت":"✉️ تیکت به مدیریت",
 "🔄 شروع دوباره":"🔄 شروع مجدد","Start again":"🔄 شروع مجدد","Restart":"🔄 شروع مجدد",
 "🪪 FIDA service":"🪪 فیدای غیر حضوری","🖨 Printing":"🖨 خدمات چاپ","📱 SIM services":"📱 خدمات سیم کارت","🎫 Tracking":"🎫 پیگیری",
}

def clean(s):
 s=str(s or '').strip()
 for p in ('🟢 ','🟠 ','🟣 ','🟡 ','⚪ ','🔷 ','🟦 ','🟩 ','🟨 ','🔵 '):
  if s.startswith(p): s=s[len(p):].strip()
 return ALIASES.get(s,s)

def label(q):
 try:
  import telegram_no_reply_keyboard as N
  v=N._ACTIONS.get(str(q.data))
  if v:return clean(v)
 except Exception: pass
 try:
  for row in getattr(getattr(q.message,'reply_markup',None),'inline_keyboard',[]) or []:
   for b in row:
    if str(getattr(b,'callback_data',''))==str(q.data): return clean(getattr(b,'text',''))
 except Exception: pass
 return ''

def proxy(update,q,text):
 src=q.message
 class M:
  def __init__(self,x,t): self._x=x; self.text=t
  def __getattr__(self,n): return getattr(self._x,n)
 m=M(src,text)
 return SimpleNamespace(update_id=getattr(update,'update_id',None),message=m,effective_message=m,effective_user=q.from_user,effective_chat=getattr(src,'chat',None),callback_query=q)

async def click(update,context,B):
 q=update.callback_query
 if not q:return
 await q.answer(); t=label(q); uid=q.from_user.id; st=B.S.setdefault(uid,{})
 if not t:
  await q.message.reply_text('⛔ این گزینه فعلاً بسته یا نامعتبر است. لطفاً از منوی فعلی استفاده کنید.'); raise ApplicationHandlerStop
 try:
  if t=='🔄 شروع مجدد':
   old=dict(st); B.S[uid]={'lang':old.get('lang','fa')}; status=old.get('status') or old.get('citizenship')
   if status:B.S[uid].update(status=status,citizenship=status)
   await B.start(proxy(update,q,'/start'),context); raise ApplicationHandlerStop
  if t=='❌ انصراف': await B.cancel(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='👥 پنل همکاران': await B.partner(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='🛠 پنل مدیریت بات':
   if not B.admin(uid): await q.message.reply_text('⛔ این بخش فقط برای مدیریت فعال است.'); raise ApplicationHandlerStop
   fn=getattr(B,'admin_text',None)
   if fn: await fn(proxy(update,q,t),context)
   else: await q.message.reply_text('🛠 پنل مدیریت',reply_markup=B.amenu())
   raise ApplicationHandlerStop
  if t=='📱 خدمات سیم کارت':
   fn=getattr(B,'sim_start',None)
   if fn: await fn(proxy(update,q,t),context)
   else: await q.message.reply_text('⛔ خدمات سیم کارت فعلاً بسته است.')
   raise ApplicationHandlerStop
  if t=='🪪 فیدای غیر حضوری': await B.fida(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='🖨 خدمات چاپ': await B.prt(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='🪪 حل مشکل ورود اتباع دولت من': await B.gov(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='🚪 خروج از پنل': await B.partner_exit(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='📋 سوابق': await B.phistory(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='🔎 پیگیری کد': await B.ptrack(proxy(update,q,t),context); raise ApplicationHandlerStop
  if t=='💰 موجودی':
   p=B.db.conn.execute('SELECT balance FROM partners WHERE id=? AND active=1',(st.get('partner_id'),)).fetchone()
   await q.message.reply_text(f"💰 موجودی شما: {int(p['balance'] or 0):,} تومان" if p else '⛔ حساب همکار فعال نیست.',reply_markup=B.partner_kb(st.get('lang','fa'))); raise ApplicationHandlerStop
  if t=='➕ شارژ حساب':
   fn=getattr(B,'topup',None)
   if fn: await fn(proxy(update,q,t),context)
   else: await q.message.reply_text('⛔ شارژ حساب فعلاً بسته است.',reply_markup=B.partner_kb(st.get('lang','fa')))
   raise ApplicationHandlerStop
  if t=='✉️ تیکت به مدیریت':
   if not st.get('partner_id'): await q.message.reply_text('⛔ ابتدا وارد پنل همکاران شوید.'); raise ApplicationHandlerStop
   st['mode']='partner_message'; await q.message.reply_text('✉️ متن تیکت خود را ارسال کنید.\n\nبرای لغو، «❌ انصراف» را بزنید.',reply_markup=B.cancel_kb(st.get('lang','fa'))); raise ApplicationHandlerStop
  service_map={'🎫 کد رهگیری تمدید کارت‌ها':'renewal','📝 آزمون غربالگری':'screening','🎫 پیگیری':'tracking','💰 کیف پول من':'wallet','📞 تماس با ما':'contact','📝 ثبت شکایت مشتریان':'complaint'}
  if t in service_map:
   row=B.db.conn.execute('SELECT active FROM services WHERE key=?',(service_map[t],)).fetchone()
   if not row or not int(row['active']): await q.message.reply_text('⛔ این خدمت فعلاً بسته می‌باشد.',reply_markup=B.main(uid)); raise ApplicationHandlerStop
  result=await B.router(proxy(update,q,t),context)
  if result is None: await q.message.reply_text('⛔ این گزینه فعلاً بسته می‌باشد.',reply_markup=B.main(uid))
 except ApplicationHandlerStop: raise
 except Exception:
  log.exception('absolute Telegram callback failed: %s',t)
  await q.message.reply_text('❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره تلاش کنید.')
 raise ApplicationHandlerStop

def install(app,B):
 if getattr(B,'_telegram_absolute_fix',False): return
 def main(uid):
  rows=[["🪪 فیدای غیر حضوری","🖨 خدمات چاپ"],["🪪 حل مشکل ورود اتباع دولت من","🎫 کد رهگیری تمدید کارت‌ها"],["📱 خدمات سیم کارت","📝 آزمون غربالگری"],["🎫 پیگیری","💰 کیف پول من"],["📞 تماس با ما","📝 ثبت شکایت مشتریان"]]
  if B.admin(uid): rows.append(["🛠 پنل مدیریت بات"])
  rows += [["👥 پنل همکاران"],[B.CANCEL],["🔄 شروع مجدد"]]
  return B.kb(rows)
 def partner_kb(lang='fa'):
  return B.kb([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["📱 خدمات سیم کارت","🔎 پیگیری کد"],["📋 سوابق","💰 موجودی"],["✉️ تیکت به مدیریت"],["🚪 خروج از پنل"],[B.CANCEL]])
 B.main=main; B.partner_kb=partner_kb
 app.add_handler(CallbackQueryHandler(lambda u,c: click(u,c,B),pattern=r'^ik:'),group=-4000)
 B._telegram_absolute_fix=True
 log.info('Absolute Telegram callback/navigation fix installed')
