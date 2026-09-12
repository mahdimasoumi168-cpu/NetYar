"""Unified Government access flow for citizens/partners.

Document types: Amayesh card, passport, residence booklet. Family code is
requested only for Amayesh. Passport number is replaced by residence-booklet
number for the residence-booklet path. Postal code is collected at the end.
"""
import re
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,MessageHandler,filters

def digits(v):return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def doc_menu():return InlineKeyboardMarkup([[InlineKeyboardButton("🪪 کارت آمایش",callback_data="govv2:card"),InlineKeyboardButton("🛂 گذرنامه",callback_data="govv2:passport")],[InlineKeyboardButton("📗 دفترچه اقامت",callback_data="govv2:residence")],[InlineKeyboardButton("❌ انصراف",callback_data="govv2:cancel")]])
def cancel():return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data="govv2:cancel")]])

def start_state(B,uid):
 old=B.S.get(uid,{})
 B.S[uid]={"mode":"govv2_phone","lang":old.get("lang","fa"),"partner_id":old.get("partner_id"),"govv2":{}}

def install(app,B):
 if getattr(B,"_gov_v2",False):return
 async def start(update,context):
  uid=update.effective_user.id;start_state(B,uid);return await update.effective_message.reply_text("🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=doc_menu())
 B.gov=start
 async def cb(update,context):
  q=update.callback_query;d=(q.data or "").split(":")
  if not q or len(d)<2 or d[0]!="govv2":return
  await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{})
  if d[1]=="cancel":return await B.cancel(update,context)
  st["gov_doc_type"]={"card":"card","passport":"passport","residence":"residence_booklet"}[d[1]];st["mode"]="govv2_phone";return await q.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:",reply_markup=cancel())
 async def text(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{})
  mode=st.get("mode");t=(update.message.text or "").strip();d=digits(t)
  if mode=="govv2_phone":
   p=re.sub(r"\D","",d)
   if p.startswith("98"):p="0"+p[2:]
   if not re.fullmatch(r"09\d{9}",p):return await update.message.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.",reply_markup=cancel())
   st["gov_phone"]=p;st["mode"]="govv2_dob";return await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:",reply_markup=cancel())
  if mode=="govv2_dob":st["gov_dob"]=t;st["mode"]="govv2_unique";return await update.message.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:",reply_markup=cancel())
  if mode=="govv2_unique":st["gov_unique"]=t;st["mode"]="govv2_special";return await update.message.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:",reply_markup=cancel())
  if mode=="govv2_special":
   if not re.fullmatch(r"1\d{11}",d):return await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.",reply_markup=cancel())
   st["gov_special"]=d
   if st.get("gov_doc_type")=="card":st["mode"]="govv2_family";return await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (فقط برای کارت آمایش):",reply_markup=cancel())
   st["mode"]="govv2_identity_number";return await update.message.reply_text("🛂 شماره گذرنامه مشترک را وارد کنید:" if st.get("gov_doc_type")=="passport" else "📗 شماره دفترچه اقامت مشترک را وارد کنید:",reply_markup=cancel())
  if mode=="govv2_family":
   if not d.isdigit():return await update.message.reply_text("❌ کد خانوار باید عددی باشد.",reply_markup=cancel())
   st["gov_family_code"]=d;st["mode"]="govv2_postal";return await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel())
  if mode=="govv2_identity_number":
   if len(t)<3:return await update.message.reply_text("❌ شماره مدرک را صحیح وارد کنید.",reply_markup=cancel())
   st["gov_identity_number"]=t;st["mode"]="govv2_postal";return await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel())
  if mode=="govv2_postal":
   if not re.fullmatch(r"\d{10}",d):return await update.message.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.",reply_markup=cancel())
   st["gov_postal"]=d;st["mode"]="govv2_photo";return await update.message.reply_text("📸 حالا تصویر مدرک مشترک را ارسال کنید:",reply_markup=cancel())
 async def media(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{})
  if st.get("mode")!="govv2_photo":return
  msg=update.message;fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
  if not fid:return
  amount=int(B.db.setting("price_government","500000") or 500000);pid=st.get("partner_id");p=B.db.conn.execute("SELECT * FROM partners WHERE id=?",(pid,)).fetchone() if pid else None
  if pid and (not p or int(p["balance"] or 0)<amount):return await msg.reply_text(f"❌ اعتبار کافی نیست.\n💰 هزینه: {amount:,} تومان\n💳 اعتبار: {int(p['balance'] if p else 0):,} تومان",reply_markup=B.partner_kb())
  owner=pid or B.db.user("telegram",uid,update.effective_user.username,update.effective_user.full_name);rid,code=B.db.create_request(owner,"government","telegram",amount)
  fields=[("doc_type",st.get("gov_doc_type")),("phone",st.get("gov_phone")),("dob",st.get("gov_dob")),("unique_id",st.get("gov_unique")),("special_id",st.get("gov_special")),("postal_code",st.get("gov_postal"))]
  if st.get("gov_doc_type")=="card":fields.append(("family_code",st.get("gov_family_code")))
  if st.get("gov_doc_type")=="passport":fields.append(("passport",st.get("gov_identity_number")))
  if st.get("gov_doc_type")=="residence_booklet":fields.append(("booklet_number",st.get("gov_identity_number")))
  for k,v in fields:
   if v:B.db.answer(rid,k,answer=v)
  B.db.answer(rid,"document",file_id=fid)
  if pid:
   B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),pid));B.db.conn.commit();left=int(p["balance"])-amount
  else:B.db.conn.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit();left=None
  typ={"card":"کارت آمایش","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}.get(st.get("gov_doc_type"),"-")
  text=(f"👔 مدیر — درخواست جدید\n🆕 حل مشکل سامانه دولت من\n🎫 {code}\n🪪 مدرک: {typ}\n📱 موبایل مشترک: {st.get('gov_phone','-')}\n🎂 تاریخ تولد: {st.get('gov_dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی: {st.get('gov_special','-')}\n"+(f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family_code','-')}\n" if st.get('gov_doc_type')=="card" else "")+(f"🛂 شماره پاسپورت: {st.get('gov_identity_number','-')}\n" if st.get('gov_doc_type')=="passport" else f"📗 شماره دفترچه اقامت: {st.get('gov_identity_number','-')}\n" if st.get('gov_doc_type')=="residence_booklet" else "")+f"📮 کد پستی: {st.get('gov_postal','-')}\n💰 مبلغ: {amount:,} تومان\n"+(f"💳 کسر از اعتبار همکار: {amount:,} تومان\n💵 اعتبار باقی‌مانده: {left:,} تومان\n" if pid else ""))
  controls=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 جزئیات کامل",callback_data=f"rq:detail:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")],[InlineKeyboardButton("⏳ بررسی",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"rq:approve:{rid}")],[InlineKeyboardButton("❌ رد",callback_data=f"rq:reject:{rid}")]])
  for aid in B.ADM:
   try:
    if msg.photo:await context.bot.send_photo(int(aid),fid,caption=text,reply_markup=controls)
    else:await context.bot.send_document(int(aid),fid,caption=text,reply_markup=controls)
   except Exception:pass
  st["mode"]=None;return await msg.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}"+(f"\n💳 مبلغ کسرشده: {amount:,} تومان\n💵 اعتبار باقی‌مانده: {left:,} تومان" if pid else ""),reply_markup=B.partner_kb() if pid else B.main(uid))
 app.add_handler(CallbackQueryHandler(cb,pattern=r"^govv2:"),group=-70)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:text(u,c,B)),group=-69)
 app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,lambda u,c:media(u,c,B)),group=-69)
 B._gov_v2=True
