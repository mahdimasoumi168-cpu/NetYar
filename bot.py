import os,logging
from telegram import Update,ReplyKeyboardMarkup,InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import Application,CommandHandler,MessageHandler,CallbackQueryHandler,filters
from core import db,now,check_password
logging.basicConfig(level=logging.INFO); S={}; CANCEL="❌ انصراف"; OK="✅ تأیید"
ADM={x.strip() for x in os.getenv("ADMIN_IDS","").replace(";",",").split(",") if x.strip()}
ADMIN_COMMAND=os.getenv("ADMIN_COMMAND", "/"+"Admin"+"2025").strip()
def admin(u): return str(u) in ADM or S.get(u,{}).get("admin") is True
def kb(rows): return ReplyKeyboardMarkup(rows,resize_keyboard=True)
def L(uid, fa, en, ar):
 lang=S.get(uid,{}).get("lang","fa")
 return {"fa":fa,"en":en,"ar":ar}.get(lang,fa)
def main(uid):
 lang=S.get(uid,{}).get("lang","fa")
 labels={
  "fa":["🪪 فیدای غیر حضوری","🖨 خدمات چاپ","🪪 حل مشکل ورود اتباع دولت من","🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری","💰 کیف پول من","📞 تماس با ما","📝 ثبت شکایت مشتریان","👥 پنل همکاران"],
  "en":["🪪 FIDA non-in-person","🖨 Printing service","🏛 Government access issue","🎫 Track request","📱 SIM services","📝 Screening & follow-up","💰 My wallet","📞 Contact us","📝 Customer complaint","👥 Partner panel"],
  "ar":["🪪 خدمة فيدا","🖨 خدمة الطباعة","🏛 مشكلة خدمات الحكومة","🎫 متابعة الطلب","📱 خدمات الشريحة","📝 الفحص والمتابعة","💰 محفظتي","📞 اتصل بنا","📝 شكوى العميل","👥 لوحة الشركاء"]
 }
 a=labels.get(lang,labels["fa"])
 rows=[[a[0],a[1]],[a[2],a[3]],[a[4],a[5]],[a[6],a[7]],[a[8]]]
 if admin(uid): rows.append(["🛠 پنل مدیریت بات"])
 rows.extend([["❌ Cancel" if lang=="en" else "❌ إلغاء" if lang=="ar" else CANCEL],[a[9]]])
 return kb(rows)
def cancel_kb(lang="fa"):
 return kb([[CANCEL if lang=="fa" else "❌ Cancel" if lang=="en" else "❌ إلغاء"]])
def partner_kb(lang="fa"):
 if lang=="en": return kb([["➕ Top up","🪪 Partner request"],["🔎 Track code","📋 History"],["❌ Cancel"]])
 if lang=="ar": return kb([["➕ شحن الحساب","🪪 طلب الشريك"],["🔎 رمز المتابعة","📋 السجل"],["❌ إلغاء"]])
 return kb([["➕ شارژ حساب","🪪 ثبت درخواست همکار"],["🔎 پیگیری کد","📋 سوابق"],[CANCEL]])
def amenu(): return kb([["👥 همکاران","💰 شارژها"],["💰 پرداخت‌های مشتری","📋 درخواست‌ها"],["⚙️ قیمت‌ها","📊 گزارش"],["⬅️ منوی اصلی"]])
async def start(u,c):
 uid=u.effective_user.id; db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name); S[uid]={}
 await u.message.reply_text("سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید / Choose your language / اختر اللغة:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))
async def langcb(u,c):
 q=u.callback_query; await q.answer(); uid=q.from_user.id; lang=q.data.split(":")[1]; S[uid]={"lang":lang}
 cit={"fa":"آیا اتباع هستید یا ایرانی؟","en":"Are you a foreign national or Iranian?","ar":"هل أنت من الرعايا الأجانب أم إيراني؟"}[lang]
 foreign={"fa":"🪪 اتباع هستم","en":"🪪 Foreign national","ar":"🪪 أجنبي"}[lang]
 iran={"fa":"🇮🇷 ایرانی هستم","en":"🇮🇷 Iranian","ar":"🇮🇷 إيراني"}[lang]
 await q.message.reply_text(cit,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(foreign,callback_data="st:foreign"),InlineKeyboardButton(iran,callback_data="st:iranian")]]))
async def statuscb(u,c):
 q=u.callback_query; await q.answer(); uid=q.from_user.id; S.setdefault(uid,{})["status"]=q.data.split(":")[1]
 lang=S[uid].get("lang","fa")
 if S[uid]["status"]=="iranian":
  msg={"fa":"🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.","en":"🇮🇷 Services are currently unavailable for Iranian users.","ar":"🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين."}[lang]
  partner={"fa":"👥 پنل همکاران","en":"👥 Partner panel","ar":"👥 لوحة الشركاء"}[lang]
  track={"fa":"🎫 پیگیری","en":"🎫 Track","ar":"🎫 متابعة"}[lang]
  cancel={"fa":CANCEL,"en":"❌ Cancel","ar":"❌ إلغاء"}[lang]
  return await q.message.reply_text(msg,reply_markup=kb([[partner,track],[cancel]]))
 msg={"fa":"منوی خدمات کمک یار مهاجر 👇","en":"Mohajer Helper services 👇","ar":"خدمات مساعد المهاجر 👇"}[lang]
 await q.message.reply_text(msg,reply_markup=main(uid))
async def cancel(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{}); partner_id=st.get("partner_id"); lang=st.get("lang","fa")
 S[uid]={"status":"foreign","lang":lang,"partner_id":partner_id} if partner_id else {"status":"foreign","lang":lang}
 msg={"fa":"عملیات لغو شد. به منوی اصلی برگشتید. ✅","en":"Operation cancelled. Back to the main menu. ✅","ar":"تم إلغاء العملية والعودة إلى القائمة الرئيسية. ✅"}[lang]
 await u.message.reply_text(msg,reply_markup=partner_kb(lang) if partner_id else main(uid))
async def partner(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{})
 if st.get("partner_id"):
  p=db.conn.execute("SELECT * FROM partners WHERE id=?",(st["partner_id"],)).fetchone()
  return await u.message.reply_text(f"👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 اعتبار: {p['balance']:,} تومان",reply_markup=partner_kb())
 st["mode"]="p_phone"; await u.message.reply_text("📱 شماره همراه همکار را وارد کنید:",reply_markup=cancel_kb())
async def ptext(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{}); t=(u.message.text or "").strip()
 if st.get("mode")=="p_phone":
  p=db.partner(t)
  if not p:return await u.message.reply_text(L(uid,"❌ همکار یافت نشد.","❌ Partner not found.","❌ لم يتم العثور على الشريك."))
  st["phone"]=t; st["mode"]="p_pass"; return await u.message.reply_text("🔐 رمز عبور را وارد کنید:",reply_markup=cancel_kb())
 if st.get("mode")=="p_pass":
  p=db.partner(st["phone"])
  if not p or not check_password(t,p["password_hash"]):return await u.message.reply_text(L(uid,"❌ اطلاعات ورود نادرست است.","❌ Invalid phone number or password.","❌ رقم الهاتف أو كلمة المرور غير صحيحة."))
  st["partner_id"]=p["id"]; st["mode"]=None; return await partner(u,c)
 if st.get("mode")=="topup_amount":
  try:a=int(t.replace(",","").replace("٬",""))
  except:return await u.message.reply_text(L(uid,"مبلغ را عددی وارد کنید.","Enter the amount as a number.","أدخل المبلغ كرقم."))
  if a<=0:return await u.message.reply_text(L(uid,"مبلغ نامعتبر است.","Invalid amount.","المبلغ غير صالح."))
  st["amount"]=a; st["mode"]="topup_receipt"; return await u.message.reply_text(f"💳 مبلغ: {a:,} تومان\nشماره کارت: {db.setting('card_number')}\nبه نام: {db.setting('card_owner')}\n📸 رسید را ارسال کنید.",reply_markup=cancel_kb())
 if st.get("mode")=="ptrack":
  r=db.conn.execute("SELECT * FROM requests WHERE tracking_code=? AND user_id=?",(t,st["partner_id"])).fetchone()
  return await u.message.reply_text(f"🎫 {r['tracking_code']}\nوضعیت: {r['status']}\nمبلغ: {r['amount']:,} تومان" if r else "❌ کد پیدا نشد.",reply_markup=partner_kb())
 if st.get("mode")=="price":
  a=t.split()
  if len(a)!=2 or not a[1].isdigit():return await u.message.reply_text("مثال: government 500000")
  db.set_setting("price_"+a[0],int(a[1])); return await u.message.reply_text("قیمت ذخیره شد. ✅",reply_markup=amenu())
async def topup(u,c): S[u.effective_user.id]["mode"]="topup_amount"; await u.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:",reply_markup=cancel_kb())
async def ptrack(u,c): S[u.effective_user.id]["mode"]="ptrack"; await u.message.reply_text("🎫 کد پیگیری را ارسال کنید:",reply_markup=cancel_kb())
async def phistory(u,c):
 st=S.get(u.effective_user.id,{})
 if not st.get("partner_id"):return await u.message.reply_text(L(uid,"ابتدا وارد پنل همکاران شوید.","Please log in to the partner panel first.","يرجى تسجيل الدخول إلى لوحة الشركاء أولاً."))
 rows=db.conn.execute("SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20",(st["partner_id"],)).fetchall()
 await u.message.reply_text("\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,}" for r in rows) or "سابقه‌ای نیست.",reply_markup=partner_kb())
async def media(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{})
 fid=u.message.photo[-1].file_id if u.message.photo else (u.message.document.file_id if u.message.document else "")
 if st.get("mode")=="topup_receipt":
  if not fid:return await u.message.reply_text("رسید را به صورت عکس/فایل بفرستید.")
  tid=db.add_topup(st["partner_id"],st["amount"],fid); st["mode"]=None; return await u.message.reply_text(f"رسید شارژ #{tid} ثبت شد و منتظر تأیید مدیر است. ✅",reply_markup=partner_kb())
 if st.get("mode")=="fida_doc":
  if not fid:return await u.message.reply_text("تصویر مدرک را بفرستید.")
  st["doc"]=fid; st["mode"]="fida_phone"; return await u.message.reply_text("📱 شماره موبایل مشترک را وارد کنید.",reply_markup=cancel_kb())
 if st.get("mode")=="gov_doc":
  if not fid:return await u.message.reply_text("تصویر را بفرستید.")
  st["gov_files"][st["field"]]=fid
  if st["field"]=="id": st["field"]="sim"; return await u.message.reply_text("📄 اگر سند سیم‌کارت دارید بفرستید؛ اگر ندارید «ندارم» بنویسید.",reply_markup=cancel_kb())
  st["mode"]="gov_phone"; return await u.message.reply_text(L(uid,"📱 لطفاً شماره موبایل مشترک را وارد کنید.","📱 Enter the customer's mobile number.","📱 أدخل رقم هاتف العميل."),reply_markup=cancel_kb(S.get(uid,{}).get("lang","fa")))
 if st.get("mode")=="print":
  if not fid:return await u.message.reply_text("عکس یا فایل بفرستید.")
  st.setdefault("files",[]).append(fid); return await u.message.reply_text(f"📎 دریافت شد ({len(st['files'])}). برای پایان «تأیید» را بزنید.",reply_markup=kb([[OK,CANCEL]]))
 if st.get("mode")=="payment":
  if not fid:return await u.message.reply_text("رسید را ارسال کنید.")
  db.conn.execute("UPDATE requests SET payment_status='pending',status='payment_review',payment_note=? WHERE id=?",(fid,st["rid"])); db.conn.commit(); code=st["code"]; st["mode"]=None
  return await u.message.reply_text(f"✅ رسید دریافت شد.\n🎫 کد پیگیری: {code}\nمنتظر بررسی مدیر باشید.",reply_markup=main(uid))
async def fida(u,c):
 uid=u.effective_user.id; S[uid]={"mode":"fida_doc","status":"foreign","lang":S.get(uid,{}).get("lang","fa"),"partner_id":S.get(uid,{}).get("partner_id")}; await u.message.reply_text("🪪 عکس مدرک شناسایی را ارسال کنید.",reply_markup=cancel_kb())
async def gov(u,c):
 uid=u.effective_user.id; S[uid]={"mode":"gov_text","status":"foreign","lang":S.get(uid,{}).get("lang","fa"),"gov_files":{},"field":"fida","partner_id":S.get(uid,{}).get("partner_id")}; await u.message.reply_text("🆔 شناسه فیدا را وارد کنید.",reply_markup=cancel_kb())
async def prt(u,c):
 uid=u.effective_user.id; S[uid]={"mode":"print_color","status":"foreign","lang":S.get(uid,{}).get("lang","fa"),"files":[],"partner_id":S.get(uid,{}).get("partner_id")}; await u.message.reply_text("🖨 نوع چاپ:",reply_markup=kb([["⚫ سیاه و سفید","🌈 رنگی"],[CANCEL]]))
async def service_text(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{}); t=(u.message.text or "").strip()
 if st.get("mode")=="fida_phone":
  amount=int(db.setting("price_fida","0")); rid,code=db.create_request(st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name),"fida","telegram",amount); db.answer(rid,"document",file_id=st["doc"]); db.answer(rid,"phone",st["phone"])
  if st.get("partner_id"):
   p=db.conn.execute("SELECT * FROM partners WHERE id=?",(st["partner_id"],)).fetchone()
   if p and p["balance"]>=amount: db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance' WHERE id=?",(rid,)); db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,now(),p["id"])); db.conn.commit(); st["mode"]=None; return await u.message.reply_text(f"✅ ثبت شد.\n🎫 {code}\n💰 کسر: {amount:,} تومان",reply_markup=partner_kb())
  st.update({"rid":rid,"code":code,"mode":"payment"}); return await invoice(u,amount,code)
 if st.get("mode")=="gov_text":
  if st["field"]=="fida":st["gov_files"]["fida_id"]=t;st["field"]="yekta";return await u.message.reply_text(L(uid,"🔢 شناسه یکتای مشترک را وارد کنید.","🔢 Enter the customer's unique ID.","🔢 أدخل المعرف الفريد للعميل."),reply_markup=cancel_kb(S.get(uid,{}).get("lang","fa")))
  if st["field"]=="yekta":st["gov_files"]["yekta"]=t;st["field"]="id";st["mode"]="gov_doc";return await u.message.reply_text("🪪 تصویر مدرک شناسایی را بفرستید.",reply_markup=cancel_kb())
 if st.get("mode")=="gov_doc" and st.get("field")=="sim" and t=="ندارم":st["gov_files"]["sim"]="ندارد";st["mode"]="gov_phone";return await u.message.reply_text("📱 شماره موبایل مشتری را بفرستید.",reply_markup=cancel_kb())
 if st.get("mode")=="gov_phone":
  st["gov_phone"]=t; st["mode"]="gov_dob"; return await u.message.reply_text(L(uid,"🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.","🎂 Enter the customer's birth date as 1356/01/01.","🎂 أدخل تاريخ ميلاد العميل بالشكل 1356/01/01."),reply_markup=cancel_kb(S.get(uid,{}).get("lang","fa")))
 if st.get("mode")=="gov_dob":
  import re
  if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])",t): return await u.message.reply_text(L(uid,"❌ تاریخ تولد را به شکل 1356/01/01 وارد کنید.","❌ Enter the birth date as 1356/01/01.","❌ أدخل تاريخ الميلاد بالشكل 1356/01/01."),reply_markup=cancel_kb(S.get(uid,{}).get("lang","fa")))
  st["dob"]=t; amount=int(db.setting("price_government","500000")); rid,code=db.create_request(st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name),"government","telegram",amount)
  for k,v in st["gov_files"].items():db.answer(rid,k,file_id=v if k in ("id","sim") and v!="ندارد" else "",answer=v if k not in ("id","sim") or v=="ندارد" else "")
  db.answer(rid,"phone",t)
  if st.get("partner_id"):
   p=db.conn.execute("SELECT * FROM partners WHERE id=?",(st["partner_id"],)).fetchone()
   if not p or p["balance"]<amount:return await u.message.reply_text(f"❌ اعتبار کافی نیست. هزینه {amount:,} تومان است.",reply_markup=partner_kb())
   db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance' WHERE id=?",(rid,));db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,now(),p["id"]));db.conn.commit();st["mode"]=None;return await u.message.reply_text(f"✅ ثبت شد.\n🎫 {code}\n💰 کسر: {amount:,} تومان",reply_markup=partner_kb())
  st.update({"rid":rid,"code":code,"mode":"payment"});return await invoice(u,amount,code)
 if st.get("mode")=="print_color":
  if t in ("⚫ سیاه و سفید","🌈 رنگی"):st["color"]="bw" if t.startswith("⚫") else "color";st["mode"]="print_side";return await u.message.reply_text(L(uid,"📄 یک‌رو یا 🔄 پشت‌ورو؟","📄 Single-sided or 🔄 double-sided?","📄 وجه واحد أم 🔄 وجهان؟"),reply_markup=kb([[L(uid,"📄 یک‌رو","📄 Single-sided","📄 وجه واحد"),L(uid,"🔄 پشت‌ورو","🔄 Double-sided","🔄 وجهان")],[L(uid,CANCEL,"❌ Cancel","❌ إلغاء")]]))
 if st.get("mode")=="print_side":
  if t in ("📄 یک‌رو","🔄 پشت‌ورو"):st["side"]=1 if t.startswith("📄") else 2;st["mode"]="print_copies";return await u.message.reply_text(L(uid,"🔢 تعداد نسخه موردنیاز از هر صفحه را وارد کنید.","🔢 Enter the number of copies per page.","🔢 أدخل عدد النسخ لكل صفحة."),reply_markup=cancel_kb(S.get(uid,{}).get("lang","fa")))
 if st.get("mode")=="print_copies":
  if not t.isdigit() or int(t)<1:return await u.message.reply_text("تعداد را به عدد مثبت وارد کنید.")
  st["copies"]=int(t);st["mode"]="print";return await u.message.reply_text(L(uid,"📎 فایل‌ها را یکی‌یکی ارسال کنید؛ پایان با «تأیید».","📎 Send files/images one by one; choose Confirm when finished.","📎 أرسل الملفات أو الصور واحداً تلو الآخر، ثم اختر تأكيد عند الانتهاء."),reply_markup=kb([[L(uid,OK,"✅ Confirm","✅ تأكيد"),L(uid,CANCEL,"❌ Cancel","❌ إلغاء")]]))
 if st.get("mode")=="print" and t==OK:
  if not st["files"]:return await u.message.reply_text("حداقل یک فایل بفرستید.")
  key="price_print_color" if st["color"]=="color" else "price_print_bw";amount=len(st["files"])*int(db.setting(key,"0"))*st["copies"];rid,code=db.create_request(st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name),"print","telegram",amount)
  for i,f in enumerate(st["files"]):db.answer(rid,f"file_{i+1}",file_id=f)
  db.answer(rid,"color",st["color"]);db.answer(rid,"side",str(st["side"]));db.answer(rid,"copies",str(st["copies"]));st.update({"rid":rid,"code":code,"mode":"payment"});return await invoice(u,amount,code)
async def invoice(u,amount,code):await u.message.reply_text(f"🧾 فاکتور\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان\n\n💳 {db.setting('card_number')}\nبه نام {db.setting('card_owner')}\n\nپس از واریز رسید را ارسال کنید.",reply_markup=kb([["📸 ارسال رسید پرداخت"],[CANCEL]]))
async def admin_text(u,c):
 if not admin(u.effective_user.id):return
 t=(u.message.text or "").strip()
 if t=="👥 همکاران":rows=db.conn.execute("SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC").fetchall();return await u.message.reply_text("\n".join(f"#{r['id']} {r['name']} | {r['phone']} | {r['balance']:,}" for r in rows) or "همکاری نیست.",reply_markup=amenu())
 if t=="💰 پرداخت‌های مشتری":
  rows=db.conn.execute("SELECT id,tracking_code,service_key,amount,payment_note FROM requests WHERE payment_status='pending' ORDER BY id DESC LIMIT 30").fetchall()
  buttons=[]
  for r in rows:
   buttons.append([InlineKeyboardButton(f"#{r['id']} تأیید",callback_data=f"pay:a:{r['id']}"),InlineKeyboardButton("رد",callback_data=f"pay:r:{r['id']}")])
  txt="\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['amount']:,}" for r in rows) or "پرداخت معلقی نیست."
  return await u.message.reply_text(txt,reply_markup=InlineKeyboardMarkup(buttons) if buttons else amenu())
 if t=="💰 شارژها":rows=db.conn.execute("SELECT t.id,t.amount,t.status,p.name FROM topups t JOIN partners p ON p.id=t.partner_id ORDER BY t.id DESC LIMIT 30").fetchall();kbv=[[InlineKeyboardButton(f"#{r['id']} تأیید {r['amount']:,}",callback_data=f"tu:a:{r['id']}"),InlineKeyboardButton("رد",callback_data=f"tu:r:{r['id']}")] for r in rows if r['status']=="pending"];return await u.message.reply_text("\n".join(f"#{r['id']} {r['name']} | {r['amount']:,} | {r['status']}" for r in rows) or "شارژی نیست.",reply_markup=InlineKeyboardMarkup(kbv) if kbv else None)
 if t=="📋 درخواست‌ها":rows=db.conn.execute("SELECT tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 50").fetchall();return await u.message.reply_text("\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,} | {r['payment_status']}" for r in rows) or "درخواستی نیست.",reply_markup=amenu())
 if t=="⚙️ قیمت‌ها":S[u.effective_user.id]["mode"]="price";return await u.message.reply_text("مثال: government 500000\nfida 100000\nprint_bw 10000\nprint_color 25000",reply_markup=cancel_kb())
 if t=="⬅️ منوی اصلی": return await u.message.reply_text("منوی اصلی",reply_markup=main(u.effective_user.id))
 if t=="📊 گزارش":return await u.message.reply_text(f"همکاران: {db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0]}\nدرخواست‌ها: {db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0]}",reply_markup=amenu())
async def admin_cb(u,c):
 q=u.callback_query;await q.answer()
 if not admin(q.from_user.id):return
 parts=q.data.split(":")
 if parts[0]=="pay":
  _,a,tid=parts; r=db.conn.execute("SELECT * FROM requests WHERE id=?",(int(tid),)).fetchone()
  if not r:return
  status="paid" if a=="a" else "rejected"; req_status="submitted" if a=="a" else "payment_rejected"
  db.conn.execute("UPDATE requests SET payment_status=?,status=?,updated_at=? WHERE id=? AND payment_status='pending'",(status,req_status,now(),int(tid)));db.conn.commit()
  return await q.edit_message_text("پرداخت تأیید شد ✅" if a=="a" else "پرداخت رد شد ❌")
 _,a,tid=q.data.split(":");t=db.conn.execute("SELECT * FROM topups WHERE id=?",(int(tid),)).fetchone()
 if not t:return
 if a=="a":db.conn.execute("UPDATE topups SET status='approved',reviewed_at=? WHERE id=? AND status='pending'",(now(),tid));db.conn.execute("UPDATE partners SET balance=balance+?,updated_at=? WHERE id=?",(t["amount"],now(),t["partner_id"]));db.conn.commit();return await q.edit_message_text("شارژ تأیید شد ✅")
 db.conn.execute("UPDATE topups SET status='rejected',reviewed_at=? WHERE id=? AND status='pending'",(now(),tid));db.conn.commit();await q.edit_message_text("شارژ رد شد ❌")
async def addpartner(u,c):
 if not admin(u.effective_user.id):return
 if len(c.args)<3:return await u.message.reply_text("فرمت: /addpartner شماره رمز نام")
 try:db.add_partner(c.args[0],c.args[1]," ".join(c.args[2:]));await u.message.reply_text("همکار تعریف شد ✅")
 except:await u.message.reply_text("❌ ثبت نشد؛ شماره احتمالاً تکراری است.")
async def router(u,c):
 t=(u.message.text or "").strip();uid=u.effective_user.id
 if t==ADMIN_COMMAND:
  S.setdefault(uid,{})["admin"]=True
  return await u.message.reply_text("🛠 پنل مدیریت کامل بات\nلطفاً گزینه موردنظر را انتخاب کنید:",reply_markup=amenu())
 lang=S.get(uid,{}).get("lang","fa")
 aliases={
  "en":{"🪪 FIDA non-in-person":"🪪 فیدای غیر حضوری","🖨 Printing service":"🖨 خدمات چاپ","🏛 Government access issue":"🪪 حل مشکل ورود اتباع دولت من","🎫 Track request":"🎫 کد رهگیری تمدید کارت‌ها","📱 SIM services":"📱 خدمات سیم کارت","📝 Screening & follow-up":"📝 آزمون غربالگری و پیگیری","💰 My wallet":"💰 کیف پول من","📞 Contact us":"📞 تماس با ما","📝 Customer complaint":"📝 ثبت شکایت مشتریان","👥 Partner panel":"👥 پنل همکاران","❌ Cancel":CANCEL},
  "ar":{"🪪 خدمة فيدا":"🪪 فیدای غیر حضوری","🖨 خدمة الطباعة":"🖨 خدمات چاپ","🏛 مشكلة خدمات الحكومة":"🪪 حل مشکل ورود اتباع دولت من","🎫 متابعة الطلب":"🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات الشريحة":"📱 خدمات سیم کارت","📝 الفحص والمتابعة":"📝 آزمون غربالگری و پیگیری","💰 محفظتي":"💰 کیف پول من","📞 اتصل بنا":"📞 تماس با ما","📝 شكوى العميل":"📝 ثبت شکایت مشتریان","👥 لوحة الشركاء":"👥 پنل همکاران","❌ إلغاء":CANCEL}
 }
 t=aliases.get(lang,{}).get(t,t)
 if t==CANCEL:return await cancel(u,c)
 if t=="🛠 پنل مدیریت بات":
  if not admin(uid): return await u.message.reply_text("❌ دسترسی ندارید.")
  return await u.message.reply_text("🛠 پنل مدیریت بات",reply_markup=amenu())
 if t=="💰 کیف پول من":
  st=S.get(uid,{})
  if st.get("partner_id"):
   p=db.conn.execute("SELECT balance FROM partners WHERE id=?",(st["partner_id"],)).fetchone()
   return await u.message.reply_text(f"💰 موجودی کیف پول شما: {p['balance']:,} تومان" if p else "کیف پول یافت نشد.",reply_markup=main(uid))
  return await u.message.reply_text("💰 کیف پول پس از ورود به پنل همکاران قابل استفاده است.",reply_markup=main(uid))
 if t=="📞 تماس با ما": return await u.message.reply_text("📞 برای ارتباط با پشتیبانی با مدیریت تماس بگیرید.",reply_markup=main(uid))
 if t=="📝 ثبت شکایت مشتریان": return await u.message.reply_text("📝 ثبت شکایت مشتریان فعلاً غیرفعال است.",reply_markup=main(uid))
 if t=="👥 پنل همکاران":return await partner(u,c)
 if t=="➕ شارژ حساب":return await topup(u,c)
 if t=="🔎 پیگیری کد":return await ptrack(u,c)
 if t=="📋 سوابق":return await phistory(u,c)
 if t=="🪪 فیدای غیر حضوری":return await fida(u,c)
 if t=="🪪 حل مشکل ورود اتباع دولت من":return await gov(u,c)
 if t=="🖨 خدمات چاپ":return await prt(u,c)
 if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری"):return await u.message.reply_text("⏳ این خدمت فعلاً غیرفعال است.",reply_markup=main(uid))
 if admin(uid):return await admin_text(u,c)
 if await ptext(u,c):return
 if await service_text(u,c):return
async def admin_command(u,c):
 uid=u.effective_user.id; S.setdefault(uid,{})["admin"]=True
 await u.message.reply_text("🛠 پنل مدیریت کامل بات\nلطفاً گزینه موردنظر را انتخاب کنید:",reply_markup=amenu())
def build():
 token=os.getenv("BOT_TOKEN")
 if not token:raise RuntimeError("BOT_TOKEN is missing")
 app=Application.builder().token(token).build();app.add_handler(CommandHandler("start",start));app.add_handler(CommandHandler("addpartner",addpartner));app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),admin_command));app.add_handler(CallbackQueryHandler(langcb,pattern=r"^lang:"));app.add_handler(CallbackQueryHandler(statuscb,pattern=r"^st:"));app.add_handler(CallbackQueryHandler(admin_cb,pattern=r"^tu:"));app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media));app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,router));return app
if __name__=="__main__":
 app=build()
 webhook=os.getenv("TELEGRAM_WEBHOOK_URL","").strip()
 if webhook:
  port=int(os.getenv("PORT","8080"))
  path=webhook.rstrip("/").split("/")[-1]
  app.run_webhook(listen="0.0.0.0",port=port,url_path=path,webhook_url=webhook,allowed_updates=Update.ALL_TYPES)
 else:
  app.run_polling(allowed_updates=Update.ALL_TYPES)
