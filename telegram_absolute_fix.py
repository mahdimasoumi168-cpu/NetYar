"""Final Telegram navigation guard: controls are commands, not message content."""
import logging
from types import SimpleNamespace
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop
log=logging.getLogger("netyar.telegram.absolute_fix")
ALIASES={"🔷 👥 پنل همکاران":"👥 پنل همکاران","👥 Partner panel":"👥 پنل همکاران","👥 لوحة الشركاء":"👥 پنل همکاران","🔷 🛠 پنل مدیریت بات":"🛠 پنل مدیریت بات","🛠 Admin panel":"🛠 پنل مدیریت بات","🛠 لوحة الإدارة":"🛠 پنل مدیریت بات","📨 ارسال پیام به مدیریت":"✉️ تیکت به مدیریت","✉️ ارسال تیکت به مدیریت":"✉️ تیکت به مدیریت","📝 تیکت به مدیریت":"✉️ تیکت به مدیریت","🔄 شروع دوباره":"🔄 شروع مجدد","Start again":"🔄 شروع مجدد","Restart":"🔄 شروع مجدد"}
CONTROL={"🔄 شروع مجدد","🔄 شروع دوباره","Restart","Start again","❌ انصراف","❌ Cancel","❌ إلغاء","لغو","انصراف"}
EXIT={"🚪 خروج از پنل","🚪 خروج از پنل مدیریت","خروج از پنل","Exit panel","⬅️ منوی اصلی","🔙 منوی اصلی","بازگشت به منوی اصلی"}
def clean(v):
 t=str(v or '').strip()
 for p in ("🟢 ","🟠 ","🟣 ","🟡 ","⚪ ","🔷 ","🟦 ","🟩 ","🟨 ","🔵 "):
  if t.startswith(p): t=t[len(p):].strip()
 return ALIASES.get(t,t)
def _label(q):
 try:
  import telegram_no_reply_keyboard as k
  v=k._ACTIONS.get(str(q.data))
  if v:return clean(v)
 except Exception:pass
 try:
  for row in getattr(getattr(q,'message',None),'reply_markup',None).inline_keyboard or []:
   for b in row:
    if str(getattr(b,'callback_data',''))==str(q.data):return clean(getattr(b,'text',''))
 except Exception:pass
 return ''
def _proxy(update,q,text):
 src=q.message
 class P:
  def __init__(self,o,t):self._o,self.text=o,t
  def __getattr__(self,n):return getattr(self._o,n)
 m=P(src,text)
 return SimpleNamespace(update_id=getattr(update,'update_id',None),message=m,effective_message=m,effective_user=q.from_user,effective_chat=getattr(src,'chat',None),callback_query=q)
def _public_state(B,uid):
 old=dict(B.S.get(uid,{}));new={}
 for k in ('lang','status','citizenship','phone'):
  if old.get(k) is not None:new[k]=old[k]
 B.S[uid]=new;return new
async def _public(update,context,B,uid):
 _public_state(B,uid)
 await update.effective_message.reply_text('🏠 به منوی اصلی برگشتید.',reply_markup=B.main(uid))
async def _guard(update,context,B):
 m=update.effective_message
 if not m or not getattr(m,'text',None):return
 text=clean(m.text);uid=update.effective_user.id;st=B.S.setdefault(uid,{})
 if text in CONTROL:
  if text in {"🔄 شروع مجدد","🔄 شروع دوباره","Restart","Start again"}:
   old=dict(st);B.S[uid]={"lang":old.get('lang','fa')};status=old.get('status') or old.get('citizenship')
   if status:B.S[uid].update(status=status,citizenship=status)
   await B.start(update,context)
  else: await B.cancel(update,context)
  raise ApplicationHandlerStop
 if text in EXIT:
  await _public(update,context,B,uid);raise ApplicationHandlerStop
 if text=='➕ افزودن همکار' and B.admin(uid):
  try:
   import admin_full_v6;await admin_full_v6.admin_text(update,context)
  except Exception:
   st['mode']='admin_add_partner';st['admin_add_partner']=True
   await m.reply_text('➕ افزودن همکار\n\nفرمت:\nشماره | رمز | نام همکار\nمثال: 09xxxxxxxxx | رمز جدید | همکار اصفهان',reply_markup=B.cancel_kb())
  raise ApplicationHandlerStop
async def click(update,context,B):
 q=update.callback_query
 if not q:return
 await q.answer();text=_label(q);uid=q.from_user.id;st=B.S.setdefault(uid,{})
 if not text:raise ApplicationHandlerStop
 try:
  if text in CONTROL:
   if text in {"🔄 شروع مجدد","🔄 شروع دوباره","Restart","Start again"}:
    old=dict(st);B.S[uid]={"lang":old.get('lang','fa')};status=old.get('status') or old.get('citizenship')
    if status:B.S[uid].update(status=status,citizenship=status)
    await B.start(_proxy(update,q,'/start'),context)
   else:await B.cancel(_proxy(update,q,text),context)
   raise ApplicationHandlerStop
  if text in EXIT:await _public(_proxy(update,q,text),context,B,uid);raise ApplicationHandlerStop
  if text=='👥 پنل همکاران':await B.partner(_proxy(update,q,text),context);raise ApplicationHandlerStop
  if text=='🛠 پنل مدیریت بات':
   if not B.admin(uid):await q.message.reply_text('⛔ این بخش فقط برای مدیریت فعال است.')
   else:
    import telegram_admin_plus as A
    st['admin']=True;st['mode']=None;st['admin_plus_mode']=None
    await q.message.reply_text('🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:',reply_markup=A._admin_menu())
   raise ApplicationHandlerStop
  if text=='📱 خدمات سیم کارت':
   fn=getattr(B,'sim_start',None)
   if fn:await fn(_proxy(update,q,text),context)
   else:await q.message.reply_text('⛔ خدمات سیم کارت فعلاً در دسترس نیست.')
   raise ApplicationHandlerStop
  if text=='🪪 فیدای غیر حضوری':await B.fida(_proxy(update,q,text),context);raise ApplicationHandlerStop
  if text=='🖨 خدمات چاپ':await B.prt(_proxy(update,q,text),context);raise ApplicationHandlerStop
  if text=='🪪 حل مشکل ورود اتباع دولت من':await B.gov(_proxy(update,q,text),context);raise ApplicationHandlerStop
  if text=='📋 سوابق':await B.phistory(_proxy(update,q,text),context);raise ApplicationHandlerStop
  if text=='🔎 پیگیری کد':await B.ptrack(_proxy(update,q,text),context);raise ApplicationHandlerStop
  if text=='💰 موجودی':
   row=B.db.conn.execute('SELECT balance FROM partners WHERE id=? AND active=1',(st.get('partner_id'),)).fetchone();await q.message.reply_text(f"💰 موجودی شما: {int(row['balance'] or 0):,} تومان" if row else '⛔ حساب همکار فعال نیست.',reply_markup=B.partner_kb(st.get('lang','fa')));raise ApplicationHandlerStop
  if text=='➕ شارژ حساب':
   fn=getattr(B,'topup',None)
   if fn:await fn(_proxy(update,q,text),context)
   else:await q.message.reply_text('⛔ شارژ حساب فعلاً در دسترس نیست.',reply_markup=B.partner_kb(st.get('lang','fa')))
   raise ApplicationHandlerStop
  if text=='✉️ تیکت به مدیریت':
   if not st.get('partner_id'):await q.message.reply_text('⛔ ابتدا وارد پنل همکاران شوید.')
   else:st['mode']='partner_message';await q.message.reply_text('✉️ تیکت به مدیریت\n\nلطفاً پیام خود را ارسال کنید.\nبرای لغو «❌ انصراف» را بزنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
   raise ApplicationHandlerStop
  result=await B.router(_proxy(update,q,text),context)
  if result is None:await q.message.reply_text('⛔ این گزینه فعلاً در دسترس نیست.',reply_markup=B.main(uid))
 except ApplicationHandlerStop:raise
 except Exception:log.exception('canonical Telegram callback failed: %s',text);await q.message.reply_text('❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره تلاش کنید.')
 raise ApplicationHandlerStop
def install(app,B):
 if getattr(B,'_telegram_absolute_fix',False):return
 def main(uid):
  rows=[["🪪 فیدای غیر حضوری","🖨 خدمات چاپ"],["🪪 حل مشکل ورود اتباع دولت من","🎫 کد رهگیری تمدید کارت‌ها"],["📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری"],["🎫 پیگیری","💰 کیف پول من"],["📞 تماس با ما","📝 ثبت شکایت مشتریان"]]
  if B.admin(uid):rows.append(['🛠 پنل مدیریت بات'])
  rows.append(['👥 پنل همکاران']);return B.kb(rows)
 def partner_kb(lang='fa'):return B.kb([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🪪 فیدای غیر حضوری","📱 خدمات سیم کارت"],["🔎 پیگیری کد","📋 سوابق"],["💰 موجودی"],["✉️ تیکت به مدیریت"],["🚪 خروج از پنل"]])
 B.main=main;B.partner_kb=partner_kb
 app.add_handler(CallbackQueryHandler(lambda u,c:click(u,c,B),pattern=r'^ik:'),group=-4000)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_guard(u,c,B)),group=-3999)
 B._telegram_absolute_fix=True
 log.info('Canonical Telegram callback/navigation owner installed')
