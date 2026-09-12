"""Partner SIM-card checkout: charge partner balance instead of card transfer."""
import logging,secrets
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,MessageHandler,ApplicationHandlerStop,filters
log=logging.getLogger("netyar.telegram.sim_partner_balance")
def _kb():return InlineKeyboardMarkup([[InlineKeyboardButton("💰 پرداخت از اعتبار پنل",callback_data="sim2:partner_balance_pay")],[InlineKeyboardButton("❌ انصراف",callback_data="sim2:partner_balance_cancel")]])
def _summary(s):return f"📱 اپراتور: {s.get('carrier','-')}\n💰 مبلغ: {int(s.get('amount',0)):,} تومان\n📞 موبایل مشترک: {s.get('phone','-')}\n🔢 فیدا: {s.get('fida','-')}\n🏠 آدرس منزل: {s.get('home','-')}\n📮 کد پستی منزل: {s.get('home_post','-')}\n🏷 پلاک منزل: {s.get('home_plate','-')}\n📦 آدرس ارسال: {s.get('ship','-')}\n📮 کد پستی ارسال: {s.get('ship_post','-')}\n🏷 پلاک ارسال: {s.get('ship_plate','-')}"
async def checkout(update,context,B):
 m=update.effective_message;uid=update.effective_user.id;st=B.S.setdefault(uid,{});s=st.setdefault('sim2',{})
 if st.get('mode')!='sim2_ship_plate' or not st.get('partner_id'):return
 s['ship_plate']=(m.text or '').strip();st['mode']='sim2_partner_checkout';p=B.db.conn.execute('SELECT balance FROM partners WHERE id=? AND active=1',(st['partner_id'],)).fetchone();bal=int(p['balance']) if p else 0;amount=int(s.get('amount',0))
 await m.reply_text(f"🧾 جمع‌بندی خدمات سیم کارت\n\n{_summary(s)}\n\n💰 هزینه: {amount:,} تومان\n💳 اعتبار فعلی پنل: {bal:,} تومان\n\nدر صورت کافی بودن اعتبار، مبلغ از موجودی پنل همکار کسر می‌شود و نیازی به کارت‌به‌کارت نیست.",reply_markup=_kb());raise ApplicationHandlerStop
async def cb(update,context,B):
 q=update.callback_query;d=str(q.data or '')
 if d not in {'sim2:partner_balance_pay','sim2:partner_balance_cancel'}:return
 await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{});s=st.setdefault('sim2',{})
 if d.endswith('cancel'):st['mode']=None;return await q.message.reply_text('❌ عملیات لغو شد.',reply_markup=B.partner_kb(st.get('lang','fa')))
 if not st.get('partner_id') or st.get('mode')!='sim2_partner_checkout':return await q.message.reply_text('❌ نشست خدمات منقضی شده است. دوباره خدمات سیم کارت را شروع کنید.',reply_markup=B.partner_kb(st.get('lang','fa')))
 pid=int(st['partner_id']);amount=int(s.get('amount',0));conn=B.db.conn;p=conn.execute('SELECT * FROM partners WHERE id=? AND active=1',(pid,)).fetchone()
 if not p or int(p['balance'])<amount:return await q.message.reply_text(f"❌ اعتبار پنل کافی نیست.\n\n💳 اعتبار فعلی: {int(p['balance']) if p else 0:,} تومان\n💰 مبلغ لازم: {amount:,} تومان\n\nابتدا حساب همکار را شارژ کنید.",reply_markup=B.partner_kb(st.get('lang','fa')))
 try:
  conn.execute('BEGIN IMMEDIATE');cur=conn.execute('UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?',(amount,B.now(),pid,amount))
  if cur.rowcount!=1:raise RuntimeError('insufficient balance')
  user=conn.execute("SELECT id FROM users WHERE platform='telegram' AND external_id=?",(str(uid),)).fetchone()
  if user:user_id=user['id']
  else:
   cur=conn.execute('INSERT INTO users(platform,external_id,username,full_name,created_at,updated_at) VALUES(?,?,?,?,?,?)',('telegram',str(uid),q.from_user.username or '',q.from_user.full_name or '',B.now(),B.now()));user_id=cur.lastrowid
  code='NYM-'+secrets.token_hex(4).upper();cur=conn.execute('INSERT INTO requests(tracking_code,user_id,service_key,platform,status,amount,payment_status,payment_method,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(code,user_id,'sim_card','telegram','submitted',amount,'paid','partner_balance',B.now(),B.now()));rid=cur.lastrowid
  for k,v in {'carrier':s.get('carrier',''),'doc_type':s.get('doc',''),'phone':s.get('phone',''),'fida':s.get('fida',''),'home_address':s.get('home',''),'home_postal':s.get('home_post',''),'home_plate':s.get('home_plate',''),'shipping_address':s.get('ship',''),'shipping_postal':s.get('ship_post',''),'shipping_plate':s.get('ship_plate','')}.items():
   if v:conn.execute('INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)',(rid,k,str(v),'',B.now()))
  for i,fid in enumerate(s.get('files',[]),1):conn.execute('INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)',(rid,f'sim_document_{i}','',fid,B.now()))
  conn.commit()
 except Exception:
  try:conn.rollback()
  except Exception:pass
  return await q.message.reply_text('❌ ثبت درخواست انجام نشد؛ هیچ مبلغی از اعتبار شما کسر نشد.',reply_markup=B.partner_kb(st.get('lang','fa')))
 text='🆕 درخواست سیم کارت از پنل همکار\n\n'+_summary(s)+f'\n\n💰 مبلغ: {amount:,} تومان\n💳 پرداخت: از اعتبار پنل همکار\n🎫 کد پیگیری: {code}'
 mk=InlineKeyboardMarkup([[InlineKeyboardButton('🔎 مشاهده کامل درخواست',callback_data=f'panel:req:{rid}')],[InlineKeyboardButton('⏳ در حال بررسی',callback_data=f'panel:review:{rid}'),InlineKeyboardButton('✅ انجام شد',callback_data=f'panel:approve:{rid}')],[InlineKeyboardButton('❌ رد درخواست',callback_data=f'panel:reject:{rid}')]])
 for aid in B.ADM:
  try:
   await context.bot.send_message(chat_id=int(aid),text=text,reply_markup=mk)
   for i,fid in enumerate(s.get('files',[]),1):await context.bot.send_photo(chat_id=int(aid),photo=fid,caption=f'📎 مدرک {i} | 🎫 {code}')
  except Exception:log.exception('SIM partner notification failed')
 st['mode']=None;await q.message.reply_text(f'✅ درخواست سیم کارت ثبت شد.\n\n🎫 کد پیگیری: {code}\n💳 مبلغ از اعتبار پنل کسر شد: {amount:,} تومان',reply_markup=B.partner_kb(st.get('lang','fa')));raise ApplicationHandlerStop
def install(app,B):
 if getattr(B,'_sim_partner_balance',False):return
 app.add_handler(CallbackQueryHandler(lambda u,c:cb(u,c,B),pattern=r'^sim2:partner_balance_'),group=-5200)
 app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,lambda u,c:checkout(u,c,B)),group=-5201)
 B._sim_partner_balance=True
