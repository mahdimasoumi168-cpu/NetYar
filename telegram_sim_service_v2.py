"""Stable SIM-card purchase flow: carrier, FIDA, addresses, invoice, receipt."""
import logging, os, re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters
log=logging.getLogger("netyar.telegram.sim_v2")
PRICES={"ایرانسل":900000,"رایتل":900000,"سامانتل":560000}

def dig(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def phone(v):
 s=dig(v).strip().replace(" ","").replace("-","")
 if s.startswith("+98"): s="0"+s[3:]
 elif s.startswith("0098"): s="0"+s[4:]
 return s if re.fullmatch(r"09\d{9}",s) else None
def fida(v):
 s=dig(v).replace(" ","").replace("-","")
 return s if re.fullmatch(r"\d{12}",s) else None
def kb(rows): return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data="sim2:"+k) for k,t in r] for r in rows])
def price(B,c):
 key={"ایرانسل":"sim_price_irancell","رایتل":"sim_price_rightel","سامانتل":"sim_price_samantel"}[c]
 try:return int(B.db.setting(key,str(PRICES[c])) or PRICES[c])
 except:return PRICES[c]
def invoice(B,s):
 card=os.getenv("PAYMENT_CARD","").strip() or B.db.setting("card_number","").strip()
 owner=os.getenv("PAYMENT_CARD_OWNER","").strip() or B.db.setting("card_owner","فریبا خاوری").strip()
 return (f"💳 پرداخت فرم\n\n📱 اپراتور: {s['carrier']}\n💰 مبلغ: {s['amount']:,} تومان\n\nجمع کل\n{s['amount']:,} تومان\n\nشماره کارت: {card or 'از تنظیمات پرداخت'}\nبه نام: {owner}\n\nپس از واریز، عکس فیش را در همین گفتگو ارسال کنید.")
async def start(update,context,B):
 uid=update.effective_user.id; B.S[uid]={**B.S.get(uid,{}),"mode":"sim2_carrier","sim2":{"files":[]}}
 await update.effective_message.reply_text("📱 خدمات سیم کارت\n\nاپراتور را انتخاب کنید:",reply_markup=kb([[('ir','ایرانسل'),('rt','رایتل')],[('st','سامانتل')],[('cancel','❌ انصراف')]]))
async def cb(update,context,B):
 q=update.callback_query; d=str(q.data or '')
 if not d.startswith('sim2:'): return
 await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{});s=st.setdefault('sim2',{});a=d[5:]
 if a=='cancel': st['mode']=None; return await q.message.reply_text('❌ عملیات لغو شد.',reply_markup=B.partner_kb(st.get('lang','fa')) if st.get('partner_id') else B.main(uid))
 if a in {'ir','rt','st'}:
  c={'ir':'ایرانسل','rt':'رایتل','st':'سامانتل'}[a];s.clear();s.update(carrier=c,amount=price(B,c),files=[]);st['mode']='sim2_doc'
  return await q.message.reply_text(f"📱 {c}\n💰 {s['amount']:,} تومان\n\nنوع مدرک را انتخاب کنید:",reply_markup=kb([[('a','کارت آمایش'),('t','کارت موقت')],[('p','پاسپورت'),('b','دفترچه اقامت')],[('cancel','❌ انصراف')]]))
 if a in {'a','t','p','b'}:
  s['doc']={'a':'کارت آمایش','t':'کارت موقت','p':'پاسپورت','b':'دفترچه اقامت'}[a];st['mode']='sim2_doc_photo';return await q.message.reply_text('📸 تصویر مدرک را ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if a=='receipt': st['mode']='sim2_receipt';return await q.message.reply_text('📸 تصویر فیش واریزی را ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 raise ApplicationHandlerStop
async def text(update,context,B):
 m=update.effective_message;uid=update.effective_user.id;st=B.S.setdefault(uid,{});s=st.setdefault('sim2',{});t=(m.text or '').strip();mode=st.get('mode')
 if mode=='sim2_phone':
  p=phone(t)
  if not p:return await m.reply_text('❌ شماره موبایل معتبر نیست.',reply_markup=B.cancel_kb(st.get('lang','fa')))
  s['phone']=p;st['mode']='sim2_fida';return await m.reply_text('🔢 کد فیدای ۱۲ رقمی را وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_fida':
  x=fida(t)
  if not x:return await m.reply_text('❌ کد فیدا باید دقیقاً ۱۲ رقم باشد.',reply_markup=B.cancel_kb(st.get('lang','fa')))
  s['fida']=x;st['mode']='sim2_home';return await m.reply_text('🏠 آدرس منزل را کامل وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_home': s['home']=t;st['mode']='sim2_home_post';return await m.reply_text('📮 کد پستی منزل را وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_home_post':
  x=dig(t).replace(' ','').replace('-','')
  if not re.fullmatch(r'\d{10}',x):return await m.reply_text('❌ کد پستی باید ۱۰ رقم باشد.',reply_markup=B.cancel_kb(st.get('lang','fa')))
  s['home_post']=x;st['mode']='sim2_home_plate';return await m.reply_text('🏷 پلاک منزل را وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_home_plate': s['home_plate']=t;st['mode']='sim2_ship';return await m.reply_text('📦 آدرس ارسال را کامل وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_ship': s['ship']=t;st['mode']='sim2_ship_post';return await m.reply_text('📮 کد پستی آدرس ارسال را وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_ship_post':
  x=dig(t).replace(' ','').replace('-','')
  if not re.fullmatch(r'\d{10}',x):return await m.reply_text('❌ کد پستی باید ۱۰ رقم باشد.',reply_markup=B.cancel_kb(st.get('lang','fa')))
  s['ship_post']=x;st['mode']='sim2_ship_plate';return await m.reply_text('🏷 پلاک آدرس ارسال را وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_ship_plate':
  s['ship_plate']=t;st['mode']='sim2_invoice';return await m.reply_text(invoice(B,s),reply_markup=kb([[('receipt','📸 ارسال فیش واریزی')],[('cancel','❌ انصراف')]]))
 if mode=='sim2_invoice': return await m.reply_text(invoice(B,s),reply_markup=kb([[('receipt','📸 ارسال فیش واریزی')],[('cancel','❌ انصراف')]]))
async def media(update,context,B):
 m=update.effective_message;uid=update.effective_user.id;st=B.S.setdefault(uid,{});mode=st.get('mode','');s=st.setdefault('sim2',{})
 fid=m.photo[-1].file_id if m.photo else (m.document.file_id if m.document else '')
 if not fid:return await m.reply_text('❌ تصویر یا فایل معتبر ارسال کنید.')
 if mode=='sim2_doc_photo': s.setdefault('files',[]).append(fid);st['mode']='sim2_phone';return await m.reply_text('✅ مدرک دریافت شد.\n📱 شماره موبایل مشترک را وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
 if mode=='sim2_receipt':
  owner=st.get('partner_id') or B.db.user('telegram',uid,update.effective_user.username,update.effective_user.full_name);rid,code=B.db.create_request(owner,'sim_card','telegram',int(s.get('amount',0)))
  for k,v in {'carrier':s.get('carrier',''),'doc_type':s.get('doc',''),'phone':s.get('phone',''),'fida':s.get('fida',''),'home_address':s.get('home',''),'home_postal':s.get('home_post',''),'home_plate':s.get('home_plate',''),'shipping_address':s.get('ship',''),'shipping_postal':s.get('ship_post',''),'shipping_plate':s.get('ship_plate','')}.items():
   if v:B.db.answer(rid,k,answer=v)
  for i,x in enumerate(s.get('files',[]),1):B.db.answer(rid,f'sim_document_{i}',file_id=x)
  B.db.answer(rid,'payment_receipt',file_id=fid);B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='pending_review',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
  text=f"🆕 درخواست خرید سیم کارت\n🎫 کد پیگیری: {code}\n📱 اپراتور: {s.get('carrier','-')}\n💰 مبلغ: {int(s.get('amount',0)):,} تومان\n📞 موبایل: {s.get('phone','-')}\n🔢 فیدا: {s.get('fida','-')}\n🏠 آدرس منزل: {s.get('home','-')}\n📮 کد پستی منزل: {s.get('home_post','-')}\n🏷 پلاک منزل: {s.get('home_plate','-')}\n📦 آدرس ارسال: {s.get('ship','-')}\n📮 کد پستی ارسال: {s.get('ship_post','-')}\n🏷 پلاک ارسال: {s.get('ship_plate','-')}"
  mk=InlineKeyboardMarkup([[InlineKeyboardButton('🔎 مشاهده کامل درخواست',callback_data=f'panel:req:{rid}')],[InlineKeyboardButton('⏳ در حال بررسی',callback_data=f'panel:review:{rid}'),InlineKeyboardButton('✅ انجام شد',callback_data=f'panel:approve:{rid}')],[InlineKeyboardButton('❌ رد درخواست',callback_data=f'panel:reject:{rid}')]])
  for aid in B.ADM:
   try:
    await context.bot.send_message(chat_id=int(aid),text=text,reply_markup=mk)
    for i,x in enumerate(s.get('files',[]),1):await context.bot.send_photo(chat_id=int(aid),photo=x,caption=f'📎 مدرک {i}')
    await context.bot.send_photo(chat_id=int(aid),photo=fid,caption=f'💳 فیش واریزی | 🎫 {code}')
   except Exception:log.exception('SIM receipt forwarding failed')
  st['mode']=None;return await m.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n\nوضعیت را از گزینه «🎫 پیگیری» پیگیری کنید.",reply_markup=B.partner_kb(st.get('lang','fa')) if st.get('partner_id') else B.main(uid))
def install(app,B):
 if getattr(B,'_telegram_sim_v2',False):return
 B.sim_start=lambda u,c:start(u,c,B)
 app.add_handler(CallbackQueryHandler(lambda u,c:cb(u,c,B),pattern=r'^sim2:'),group=-3500)
 app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,lambda u,c:media(u,c,B)),group=-3499)
 app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,lambda u,c:text(u,c,B)),group=-3499)
 B._telegram_sim_v2=True
