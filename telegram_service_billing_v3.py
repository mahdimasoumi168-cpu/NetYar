"""Stable Telegram billing flows for FIDA and SIM services.
Customer: card-to-card receipt. Partner: immediate balance deduction.
"""
import logging, os, re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log=logging.getLogger("netyar.service_billing_v3")
SIM_PRICES={"سامانتل":560000,"ایرانسل":860000,"رایتل":860000}
FIDA_PRICE=400000

def dig(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def phone(v):
 s=dig(v).strip().replace(" ","").replace("-","")
 if s.startswith("+98"): s="0"+s[3:]
 elif s.startswith("0098"): s="0"+s[4:]
 return s if re.fullmatch(r"09\d{9}",s) else None
def fida_code(v):
 s=dig(v).strip().replace(" ","").replace("-","")
 return s if re.fullmatch(r"1\d{11}",s) else None
def postal(v):
 s=dig(v).strip().replace(" ","").replace("-","")
 return s if re.fullmatch(r"\d{10}",s) else None
def kb(rows): return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data="svc3:"+k) for k,t in row] for row in rows])
def card(B):
 c=os.getenv("PAYMENT_CARD","").strip() or B.db.setting("card_number","").strip()
 o=os.getenv("PAYMENT_CARD_OWNER","").strip() or B.db.setting("card_owner","").strip()
 return c,o

def _home_markup(B,uid): return B.partner_kb(B.S.get(uid,{}).get("lang","fa")) if B.S.get(uid,{}).get("partner_id") else B.main(uid)

def _price(B,key,default):
 try:return int(B.db.setting(key,str(default)) or default)
 except Exception:return default

def start_fida(B,uid,msg):
 st=B.S.setdefault(uid,{})
 st.update(mode="svc3_fida_photo",svc3={"service":"fida","files":[]})
 return msg.reply_text("🪪 فیدای غیر حضوری\n\n📸 عکس مدرک شناسایی را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))

def start_sim(B,uid,msg):
 return msg.reply_text("⛔ خدمات سیم کارت از بات حذف شده است.",reply_markup=B.main(uid))

def _partner(B,st):
 pid=st.get("partner_id")
 if not pid:return None
 return B.db.conn.execute("SELECT id,name,balance,active FROM partners WHERE id=? AND active=1",(pid,)).fetchone()

def _charge_partner(B,pid,amount):
 conn=B.db.conn
 row=conn.execute("SELECT balance FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
 if not row:return False,"❌ پنل همکاران فعال نیست."
 bal=int(row["balance"] or 0)
 if bal<amount:return False,f"❌ اعتبار پنل همکاران کافی نیست.\n\n💳 اعتبار فعلی: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان"
 conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),pid))
 return True,bal-amount

def _save_request(B,uid,st,service,amount,extra):
 pid=st.get("partner_id")
 owner=pid or B.db.user("telegram",uid,None,None)
 rid,code=B.db.create_request(owner,service,"telegram",amount)
 for k,v in extra.items():
  if v is not None and v!="": B.db.answer(rid,k,answer=str(v))
 for i,fid in enumerate(st.get("svc3",{}).get("files",[]),1): B.db.answer(rid,f"document_{i}",file_id=fid)
 return rid,code

async def _finish_fida(update,context,B,receipt=None):
 uid=update.effective_user.id;st=B.S[uid];s=st["svc3"];amount=_price(B,"price_fida",FIDA_PRICE);pid=st.get("partner_id")
 if pid:
  ok,info=_charge_partner(B,pid,amount)
  if not ok:return await update.effective_message.reply_text(info,reply_markup=B.partner_kb(st.get("lang","fa")))
  rid,code=_save_request(B,uid,st,"fida",amount,{"phone":s.get("phone"),"payment_method":"partner_balance"})
  B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
 else:
  if not receipt:return
  rid,code=_save_request(B,uid,st,"fida",amount,{"phone":s.get("phone"),"payment_method":"card_to_card"})
  B.db.answer(rid,"payment_receipt",file_id=receipt)
  B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='pending_review',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
 await B.notify_admins(context.application,f"🆕 درخواست فیدای غیرحضوری\n🎫 {code}\n👤 نام: {s.get('name','-')}\n📞 شماره در دسترس: {s.get('phone','-')}\n💰 مبلغ: {amount:,} تومان",rid)
 st["mode"]=None
 return await update.effective_message.reply_text(f"✅ درخواست فیدای غیر حضوری ثبت شد.\n🎫 کد پیگیری: {code}",reply_markup=_home_markup(B,uid))

async def cb(update,context,B):
 q=update.callback_query;d=str(q.data or "")
 if not d.startswith("svc3:"):return
 await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{});s=st.setdefault("svc3",{});a=d[5:]
 if a=="cancel":return await B.cancel(update,context)
 if a.startswith("sim_"):
  return await q.message.reply_text("⛔ خدمات سیم کارت از بات حذف شده است.",reply_markup=B.main(uid))
 if a=="sim_doc":
  st["mode"]="svc3_sim_photo";s["doc_type"]=s.get("doc_type","مدرک شناسایی")
  return await q.message.reply_text("📸 عکس مدرک شناسایی را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if a=="sim_receipt":
  st["mode"]="svc3_sim_receipt";return await q.message.reply_text("📸 عکس فیش کارت‌به‌کارت را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if a=="fida_receipt":
  st["mode"]="svc3_fida_receipt";return await q.message.reply_text("📸 عکس فیش کارت‌به‌کارت را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 raise ApplicationHandlerStop

async def text(update,context,B):
 if not update.message:return
 uid=update.effective_user.id;st=B.S.setdefault(uid,{});s=st.setdefault("svc3",{});m=st.get("mode");t=(update.message.text or "").strip()
 if m=="svc3_name":
  if len(t)<3:return await update.message.reply_text("❌ نام و نام خانوادگی را کامل وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  s["name"]=t;st["mode"]="svc3_fida" if s.get("service")=="fida" else "svc3_fida_code" if s.get("service")=="sim_card" else m
  if s.get("service")=="fida":return await update.message.reply_text("📞 شماره موبایل در دسترس را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  return await update.message.reply_text("🔢 شناسه فیدا را وارد کنید.\nباید ۱۲ رقم باشد و با عدد ۱ شروع شود.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_fida_code":
  x=fida_code(t)
  if not x:return await update.message.reply_text("❌ شناسه فیدا باید دقیقاً ۱۲ رقم باشد و با ۱ شروع شود.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  s["fida"]=x;st["mode"]="svc3_sim_photo";return await update.message.reply_text("📸 عکس مدرک شناسایی را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_fida":
  p=phone(t)
  if not p:return await update.message.reply_text("❌ شماره موبایل معتبر نیست.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  s["phone"]=p
  if st.get("partner_id"):return await _finish_fida(update,context,B)
  st["mode"]="svc3_fida_receipt";c,o=card(B);return await update.message.reply_text(f"💳 هزینه فیدای غیرحضوری: {FIDA_PRICE:,} تومان\n\nشماره کارت: {c or 'در تنظیمات ثبت نشده'}\nبه نام: {o or '-'}\n\nپس از واریز، عکس فیش را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_home":
  s["home_address"]=t;st["mode"]="svc3_home_post";return await update.message.reply_text("📮 کد پستی منزل را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_home_post":
  x=postal(t)
  if not x:return await update.message.reply_text("❌ کد پستی باید ۱۰ رقم باشد.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  s["home_postal"]=x;st["mode"]="svc3_home_plate";return await update.message.reply_text("🏷 پلاک منزل را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_home_plate":s["home_plate"]=t;st["mode"]="svc3_ship";return await update.message.reply_text("📦 آدرس ارسال سیم کارت را کامل وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_ship":s["ship_address"]=t;st["mode"]="svc3_ship_post";return await update.message.reply_text("📮 کد پستی آدرس ارسال را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_ship_post":
  x=postal(t)
  if not x:return await update.message.reply_text("❌ کد پستی باید ۱۰ رقم باشد.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  s["ship_postal"]=x;st["mode"]="svc3_ship_plate";return await update.message.reply_text("🏷 پلاک آدرس ارسال را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_ship_plate":
  s["ship_plate"]=t;st["mode"]="svc3_phone";return await update.message.reply_text("📞 یک شماره سیم کارت به نام خودتان یا یک شماره در دسترس برای ارتباط وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_phone":
  p=phone(t)
  if not p:return await update.message.reply_text("❌ شماره موبایل معتبر نیست.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  s["phone"]=p;st["mode"]="svc3_sim_pay"
  pid=st.get("partner_id")
  if pid:
   bal=B.db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1",(pid,)).fetchone();b=int(bal["balance"] or 0) if bal else 0
   return await update.message.reply_text(f"💰 هزینه: {s['amount']:,} تومان\n💳 اعتبار فعلی پنل: {b:,} تومان\n\nبرای ثبت نهایی روی تأیید هزینه بزنید.",reply_markup=kb([[('sim_partner_pay','✅ تأیید و کسر از اعتبار')],[('cancel','❌ انصراف')]]))
  c,o=card(B);return await update.message.reply_text(f"💳 هزینه: {s['amount']:,} تومان\n\nشماره کارت: {c or 'در تنظیمات ثبت نشده'}\nبه نام: {o or '-'}\n\nپس از واریز، ارسال فیش را بزنید.",reply_markup=kb([[('sim_receipt','📸 ارسال فیش واریزی')],[('cancel','❌ انصراف')]]))
 if m=="svc3_sim_pay":return
 if m=="svc3_fida_receipt":return
 if m=="svc3_sim_receipt":return

async def media(update,context,B):
 if not update.effective_message:return
 uid=update.effective_user.id;st=B.S.setdefault(uid,{});s=st.setdefault("svc3",{});m=st.get("mode")
 fid=update.effective_message.photo[-1].file_id if update.effective_message.photo else (update.effective_message.document.file_id if update.effective_message.document else "")
 if not fid or not m.startswith("svc3_"):return
 if m=="svc3_fida_photo":
  s.setdefault("files",[]).append(fid);st["mode"]="svc3_name";return await update.effective_message.reply_text("👤 نام و نام خانوادگی را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_sim_photo":
  s.setdefault("files",[]).append(fid);st["mode"]="svc3_home";return await update.effective_message.reply_text("🏠 آدرس منزل را کامل وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
 if m=="svc3_fida_receipt":return await _finish_fida(update,context,B,receipt=fid)
 if m=="svc3_sim_receipt":
  pid=st.get("partner_id");amount=int(s.get("amount",0))
  if pid:return await update.effective_message.reply_text("❌ برای پنل همکاران پرداخت کارت‌به‌کارت لازم نیست. هزینه از اعتبار کسر می‌شود.",reply_markup=B.partner_kb(st.get("lang","fa")))
  rid,code=_save_request(B,uid,st,"sim_card",amount,{"carrier":s.get("carrier"),"name":s.get("name"),"fida":s.get("fida"),"doc_type":s.get("doc_type"),"phone":s.get("phone"),"home_address":s.get("home_address"),"home_postal":s.get("home_postal"),"home_plate":s.get("home_plate"),"shipping_address":s.get("ship_address"),"shipping_postal":s.get("ship_postal"),"shipping_plate":s.get("ship_plate"),"payment_method":"card_to_card"})
  B.db.answer(rid,"payment_receipt",file_id=fid);B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='pending_review',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
  await B.notify_admins(context.application,f"🆕 درخواست سیم کارت\n🎫 {code}\n📱 {s.get('carrier')}\n👤 {s.get('name')}\n🔢 فیدا: {s.get('fida')}\n💰 مبلغ: {amount:,} تومان",rid)
  st["mode"]=None;return await update.effective_message.reply_text(f"✅ درخواست سیم کارت ثبت شد.\n🎫 کد پیگیری: {code}",reply_markup=B.main(uid))

async def pay_cb(update,context,B):
 q=update.callback_query;d=str(q.data or "")
 if d!="svc3:sim_partner_pay":return
 await q.answer("این خدمت حذف شده است.",show_alert=True)
 return await q.message.reply_text("⛔ خدمات سیم کارت از بات حذف شده است.",reply_markup=B.main(q.from_user.id))
 if not pid or not amount:return await q.message.reply_text("❌ درخواست معتبر نیست.",reply_markup=B.main(uid))
 ok,info=_charge_partner(B,pid,amount)
 if not ok:return await q.message.reply_text(info,reply_markup=B.partner_kb(st.get("lang","fa")))
 rid,code=_save_request(B,uid,st,"sim_card",amount,{"carrier":s.get("carrier"),"name":s.get("name"),"fida":s.get("fida"),"doc_type":s.get("doc_type"),"phone":s.get("phone"),"home_address":s.get("home_address"),"home_postal":s.get("home_postal"),"home_plate":s.get("home_plate"),"shipping_address":s.get("ship_address"),"shipping_postal":s.get("ship_postal"),"shipping_plate":s.get("ship_plate"),"payment_method":"partner_balance"})
 B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
 await B.notify_admins(context.application,f"🆕 درخواست سیم کارت (همکار)\n🎫 {code}\n📱 {s.get('carrier')}\n👤 {s.get('name')}\n🔢 فیدا: {s.get('fida')}\n💰 مبلغ: {amount:,} تومان",rid)
 st["mode"]=None;return await q.message.reply_text(f"✅ درخواست ثبت شد و {amount:,} تومان از اعتبار پنل کسر شد.\n🎫 کد پیگیری: {code}",reply_markup=B.partner_kb(st.get("lang","fa")))

def install(app,B):
 if getattr(B,"_svc3_installed",False):return
 B.fida=lambda u,c: start_fida(B,u.effective_user.id,u.effective_message)
 B.sim_start=lambda u,c: start_sim(B,u.effective_user.id,u.effective_message)
 app.add_handler(CallbackQueryHandler(lambda u,c: cb(u,c,B),pattern=r"^svc3:"),group=-5000)
 app.add_handler(CallbackQueryHandler(lambda u,c: pay_cb(u,c,B),pattern=r"^svc3:sim_partner_pay$"),group=-4999)
 app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,lambda u,c: media(u,c,B)),group=-5000)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c: text(u,c,B)),group=-5000)
 B._svc3_installed=True
