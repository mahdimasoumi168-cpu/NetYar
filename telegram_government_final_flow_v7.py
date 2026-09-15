"""Hardened deterministic government flow v7."""
import re
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,MessageHandler,filters,ApplicationHandlerStop
C="govv7:cancel"
def D(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def CK(): return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data=C)]])
def DK(): return InlineKeyboardMarkup([[InlineKeyboardButton("🪪 کارت آمایش",callback_data="govv7:card"),InlineKeyboardButton("🪪 کارت موقت",callback_data="govv7:temporary")],[InlineKeyboardButton("🛂 گذرنامه",callback_data="govv7:passport"),InlineKeyboardButton("📗 دفترچه اقامت",callback_data="govv7:residence")],[InlineKeyboardButton("❌ انصراف",callback_data=C)]])
def SK(): return InlineKeyboardMarkup([[InlineKeyboardButton("📱 ارسال سند سیم‌کارت",callback_data="govv7:sim_yes")],[InlineKeyboardButton("⏭ بدون سند سیم‌کارت",callback_data="govv7:sim_no")],[InlineKeyboardButton("❌ انصراف",callback_data=C)]])
def T(t): return {"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}.get(t,"-")
def F(m): return m.photo[-1].file_id if getattr(m,"photo",None) else (m.document.file_id if getattr(m,"document",None) else "")
def install(app,B):
 if getattr(B,"_gov_v7",False): return
 async def start(u,c):
  uid=u.effective_user.id; old=B.S.get(uid,{})
  if not old.get("partner_id"):
   await u.effective_message.reply_text("❌ این خدمت فقط از طریق پنل همکاران انجام می‌شود.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 پنل همکاران",callback_data="partner:panel")]])); return
  B.S[uid]={"mode":"v7_type","lang":"fa","partner_id":old.get("partner_id"),"partner_active":True}; await u.effective_message.reply_text("🏛 حل مشکل سامانه دولت من\n\n🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=DK())
 B.gov=start
 async def cb(u,c):
  q=u.callback_query
  if not q or not str(q.data or "").startswith("govv7:"): return
  await q.answer(); st=B.S.setdefault(q.from_user.id,{}); a=q.data.split(":",1)[1]
  if a=="cancel":
   pid=st.get("partner_id"); st.clear(); st.update(status="foreign",lang="fa")
   if pid: st.update(partner_id=pid,partner_active=True); await q.message.reply_text("❌ عملیات لغو شد.\n\n👥 به پنل همکاران بازگشتید.",reply_markup=B.partner_kb("fa"))
   else: await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=B.main(q.from_user.id))
   raise ApplicationHandlerStop
  if a in ("card","temporary","passport","residence"):
   st["gov_type"]={"card":"card","temporary":"temporary_card","passport":"passport","residence":"residence_booklet"}[a]; st["mode"]="v7_phone"; await q.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:",reply_markup=CK()); raise ApplicationHandlerStop
  if a=="sim_yes": st["mode"]="v7_sim"; await q.message.reply_text("📱 لطفاً سند سیم‌کارت مشترک را ارسال کنید:",reply_markup=CK()); raise ApplicationHandlerStop
  if a=="sim_no": await create(u,c,st); raise ApplicationHandlerStop
 async def text(u,c):
  m=u.message
  if not m:return
  st=B.S.setdefault(u.effective_user.id,{}); mode=st.get("mode"); d=D(m.text.strip()) if m.text else ""
  if mode not in {"v7_phone","v7_dob","v7_unique","v7_special","v7_family","v7_identity","v7_postal"}: return
  checks={"v7_phone":(r"09\d{9}","gov_phone","🎂 تاریخ تولد مشترک را وارد کنید:","❌ شماره موبایل باید دقیقاً ۱۱ رقم و با ۰۹ شروع شود."),"v7_unique":(r"9\d{9}","gov_unique","🔖 شناسه اختصاصی مشترک را وارد کنید:","❌ شناسه یکتا باید دقیقاً ۱۰ رقم و با ۹ شروع شود."),"v7_family":(r"\d{5,}","gov_family","📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:","❌ کد خانوار باید عددی و حداقل ۵ رقم باشد."),"v7_identity":(r"\d{3,}","gov_identity","📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:","❌ شماره مدرک را صحیح وارد کنید."),"v7_postal":(r"\d{10}","gov_postal","", "❌ کد پستی باید دقیقاً ۱۰ رقم باشد.")}
  if mode=="v7_phone":
   if d.startswith("98") and len(d)==12:d="0"+d[2:]
   if not re.fullmatch(r"09\d{9}",d): await m.reply_text(checks[mode][3],reply_markup=CK())
   else: st.update(gov_phone=d,mode="v7_dob"); await m.reply_text(checks[mode][2],reply_markup=CK())
  elif mode=="v7_dob":
   ok=re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])",d); st.update(gov_dob=d,mode="v7_unique") if ok else None; await m.reply_text("🎂 تاریخ تولد نامعتبر است." if not ok else "🆔 شناسه یکتای مشترک را وارد کنید:",reply_markup=CK())
  elif mode in ("v7_unique","v7_family","v7_identity"):
   p,k,nxt,err=checks[mode]; ok=re.fullmatch(p,d)
   if ok: st[k]=d; st["mode"]={"v7_unique":"v7_special","v7_family":"v7_postal","v7_identity":"v7_postal"}[mode]
   await m.reply_text(err if not ok else ("🔖 شناسه اختصاصی مشترک را وارد کنید:" if mode=="v7_unique" else nxt),reply_markup=CK())
  elif mode=="v7_special":
   ok=re.fullmatch(r"1\d{11}",d)
   if ok:
    st["gov_special"]=d; typ=st.get("gov_type"); st["mode"]="v7_family" if typ in ("card","temporary_card") else "v7_identity"; prompt="👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (حداقل ۵ رقم):" if typ in ("card","temporary_card") else ("🛂 شماره گذرنامه مشترک را وارد کنید:" if typ=="passport" else "📗 شماره دفترچه اقامت مشترک را وارد کنید:")
   else: prompt="❌ شناسه اختصاصی باید دقیقاً ۱۲ رقم و با ۱ شروع شود."
   await m.reply_text(prompt,reply_markup=CK())
  elif mode=="v7_postal":
   if not re.fullmatch(r"\d{10}",d): await m.reply_text(checks[mode][3],reply_markup=CK())
   else:
    st["gov_postal"]=d; typ=st.get("gov_type"); st["mode"]="v7_p1" if typ=="passport" else ("v7_r1" if typ=="residence_booklet" else "v7_card"); await m.reply_text("📸 ۱/۳ — عکس صفحه اول پاسپورت مشترک را ارسال کنید:" if typ=="passport" else ("📗 ۱/۲ — عکس اول دفترچه اقامت مشترک را ارسال کنید:" if typ=="residence_booklet" else "🪪 ۱/۱ — عکس مدرک مشترک را ارسال کنید:"),reply_markup=CK())
  raise ApplicationHandlerStop
 async def media(u,c):
  m=u.message; st=B.S.setdefault(u.effective_user.id,{})
  mode=st.get("mode")
  if mode not in {"v7_card","v7_p1","v7_p2","v7_p3","v7_r1","v7_r2","v7_sim"}: return
  f=F(m)
  if not f: await m.reply_text("❌ لطفاً عکس یا فایل مدرک را ارسال کنید.",reply_markup=CK()); raise ApplicationHandlerStop
  if mode=="v7_sim": st["gov_sim"]=f; await create(u,c,st); raise ApplicationHandlerStop
  if mode=="v7_card": st["gov_card"]=f; st["mode"]="v7_sim_optional"; prompt="📱 سند سیم‌کارت مشترک اختیاری است."
  elif mode=="v7_p1": st["gov_p1"]=f; st["mode"]="v7_p2"; prompt="📸 ۲/۳ — عکس صفحه تمدید پاسپورت را ارسال کنید:"
  elif mode=="v7_p2": st["gov_p2"]=f; st["mode"]="v7_p3"; prompt="📸 ۳/۳ — عکس صفحه تمدید/روادید پاسپورت را ارسال کنید:"
  elif mode=="v7_p3": st["gov_p3"]=f; st["mode"]="v7_sim_optional"; prompt="📱 سند سیم‌کارت مشترک اختیاری است."
  elif mode=="v7_r1": st["gov_r1"]=f; st["mode"]="v7_r2"; prompt="📗 ۲/۲ — عکس دوم دفترچه اقامت مشترک را ارسال کنید:"
  else: st["gov_r2"]=f; st["mode"]="v7_sim_optional"; prompt="📱 سند سیم‌کارت مشترک اختیاری است."
  await m.reply_text(prompt+"\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:",reply_markup=SK() if st["mode"]=="v7_sim_optional" else CK()); raise ApplicationHandlerStop
 async def create(u,c,st):
  pid=st.get("partner_id"); amount=int(B.db.setting("price_government","500000") or 500000); row=B.db.conn.execute("SELECT balance,active FROM partners WHERE id=?",(pid,)).fetchone() if pid else None; bal=int(row["balance"] or 0) if row else 0
  if not row or not row["active"] or bal<amount: await u.effective_message.reply_text(f"❌ اعتبار حساب همکار کافی نیست.\n💳 اعتبار: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان",reply_markup=B.partner_kb("fa")); return
  cur=B.db.conn.execute("UPDATE partners SET balance=balance-? WHERE id=? AND active=1 AND balance>=?",(amount,pid,amount)); B.db.conn.commit()
  if cur.rowcount!=1: await u.effective_message.reply_text("❌ اعتبار در لحظه ثبت درخواست کافی نبود.",reply_markup=B.partner_kb("fa")); return
  try:
   rid,code=B.db.create_request(pid,"government","telegram",amount); typ=st["gov_type"]
   vals=[("doc_type",typ),("phone",st.get("gov_phone")),("dob",st.get("gov_dob")),("unique_id",st.get("gov_unique")),("special_id",st.get("gov_special")),("postal_code",st.get("gov_postal")),("partner_id",str(pid)),("requester_telegram_id",str(u.effective_user.id))]
   if typ in ("card","temporary_card"): vals.append(("family_code",st.get("gov_family")))
   elif typ=="passport": vals.append(("passport",st.get("gov_identity")))
   else: vals.append(("booklet_number",st.get("gov_identity")))
   for k,v in vals:
    if v:B.db.answer(rid,k,answer=v)
   fs=[("document",st.get("gov_card"))] if typ in ("card","temporary_card") else ([('passport_first_page',st.get('gov_p1')),('passport_renewal_page',st.get('gov_p2')),('passport_visa_renewal_page',st.get('gov_p3'))] if typ=="passport" else [('residence_first_page',st.get('gov_r1')),('residence_renewal_page',st.get('gov_r2'))])
   if st.get("gov_sim"): fs.append(("sim_card_document",st["gov_sim"]))
   for k,f in fs:
    if f:B.db.answer(rid,k,file_id=f)
   B.db.conn.execute("UPDATE requests SET status='reviewing',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
   kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"rq:detail:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")],[InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")]])
   text=f"👔 مدیر — درخواست جدید\n🆕 حل مشکل سامانه دولت من\n🎫 کد پیگیری: {code}\n🪪 نوع مدرک: {T(typ)}\n📱 شماره موبایل مشترک: {st.get('gov_phone','-')}\n🎂 تاریخ تولد مشترک: {st.get('gov_dob','-')}\n🆔 شناسه یکتای مشترک: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی مشترک: {st.get('gov_special','-')}\n"+(f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family','-')}\n" if typ in ("card","temporary_card") else (f"🛂 شماره گذرنامه: {st.get('gov_identity','-')}\n" if typ=="passport" else f"📗 شماره دفترچه اقامت: {st.get('gov_identity','-')}\n"))+f"📮 کد پستی مشترک: {st.get('gov_postal','-')}\n💰 مبلغ: {amount:,} تومان\n💳 پرداخت: کسر خودکار از شارژ همکار"
   for aid in B.ADM:
    try: await c.bot.send_message(int(aid),text,reply_markup=kb)
    except Exception: pass
    for k,f in fs:
     if f:
      try: await c.bot.send_photo(int(aid),f,caption=f"🎫 {code}\n{k}")
      except Exception:
       try: await c.bot.send_document(int(aid),f,caption=f"🎫 {code}\n{k}")
       except Exception: pass
   st["mode"]=None; st["request_id"]=rid; st["tracking_code"]=code; await u.effective_message.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💳 مبلغ از شارژ همکار کسر شد.",reply_markup=B.partner_kb("fa"))
  except Exception:
   B.db.conn.execute("UPDATE partners SET balance=balance+? WHERE id=?",(amount,pid)); B.db.conn.commit(); raise
 app.add_handler(CallbackQueryHandler(cb,pattern=r"^govv7:"),group=-1000000); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-1000000); app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media),group=-1000000); B._gov_v7=True
