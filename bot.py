import asyncio
import os, re, logging
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from core import db, now, check_password
logging.basicConfig(level=logging.INFO)
S={}; CANCEL="❌ انصراف"; OK="✅ تأیید"
ADM={x.strip() for x in os.getenv("ADMIN_IDS","").replace(";",",").split(",") if x.strip()}
ADMIN_COMMAND=os.getenv("ADMIN_COMMAND","/Admin2025").strip()
def admin(u): return str(u) in ADM or S.get(u,{}).get("admin") is True
def kb(rows): return ReplyKeyboardMarkup(rows,resize_keyboard=True)
def L(uid,fa,en,ar): return {"fa":fa,"en":en,"ar":ar}.get(S.get(uid,{}).get("lang","fa"),fa)
def normalize_phone(v):
 s=str(v or "").strip().replace(" ","").replace("-","").replace("(","").replace(")","")
 s=s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
 if s.startswith("+98"): s="0"+s[3:]
 elif s.startswith("0098"): s="0"+s[4:]
 return s if re.fullmatch(r"09\d{9}",s) else None
def main(uid):
 a=["🪪 فیدای غیر حضوری","🖨 خدمات چاپ","🪪 حل مشکل ورود اتباع دولت من","🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری","🎫 پیگیری","💰 کیف پول من","📞 تماس با ما","📝 ثبت شکایت مشتریان","👥 پنل همکاران"]
 rows=[[a[0],a[1]],[a[2],a[3]],[a[4],a[5]],[a[6],a[7]],[a[8],a[9]]]
 if admin(uid): rows.append(["🛠 پنل مدیریت بات"])
 return kb(rows+[[CANCEL],[a[10]]])
def cancel_kb(lang="fa"): return kb([[CANCEL]])
def partner_kb(lang="fa"): return kb([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🔎 پیگیری کد","📋 سوابق"],["💰 موجودی"],[CANCEL]])
def amenu(): return kb([["👤 پنل کاربران","👥 همکاران"],["💰 شارژها","💰 پرداخت‌های مشتری"],["📋 درخواست‌ها","⚙️ قیمت‌ها"],["📊 گزارش"],["⬅️ منوی اصلی"]])
async def notify_admins(app,message,request_id=None):
 if not ADM:return
 mk=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده درخواست",callback_data=f"req:v:{request_id}"),InlineKeyboardButton("✉️ پاسخ",callback_data=f"req:r:{request_id}")]]) if request_id else None
 for aid in ADM:
  try: await app.bot.send_message(chat_id=int(aid),text=message,reply_markup=mk)
  except Exception: logging.exception("admin notification")
async def start(u,c):
 uid=u.effective_user.id; db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name); S[uid]={}
 await u.message.reply_text("سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))
async def langcb(u,c):
 q=u.callback_query; await q.answer(); uid=q.from_user.id; S[uid]={"lang":q.data.split(":")[1]}
 await q.message.reply_text("آیا اتباع هستید یا ایرانی؟",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم",callback_data="st:foreign"),InlineKeyboardButton("🇮🇷 ایرانی هستم",callback_data="st:iranian")]]))
async def statuscb(u,c):
 q=u.callback_query; await q.answer(); uid=q.from_user.id; S.setdefault(uid,{})["status"]=q.data.split(":")[1]
 await q.message.reply_text("منوی خدمات کمک یار مهاجر 👇" if S[uid]["status"]=="foreign" else "🇮🇷 خدمات ایرانی فعلاً فعال نیست.",reply_markup=main(uid))
async def cancel(u,c):
 uid=u.effective_user.id; st=S.get(uid,{}) ; partner_id=st.get("partner_id"); lang=st.get("lang","fa"); S[uid]={"status":"foreign","lang":lang,"partner_id":partner_id} if partner_id else {"status":"foreign","lang":lang}
 await u.message.reply_text("❌ عملیات لغو شد.",reply_markup=partner_kb() if partner_id else main(uid))
async def partner(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{})
 if st.get("partner_id"):
  p=db.conn.execute("SELECT * FROM partners WHERE id=?",(st["partner_id"],)).fetchone(); return await u.message.reply_text(f"👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 اعتبار: {p['balance']:,} تومان",reply_markup=partner_kb())
 st["mode"]="p_phone"; await u.message.reply_text("📱 شماره همراه همکار را وارد کنید:",reply_markup=cancel_kb())
async def ptext(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{}); t=(u.message.text or "").strip()
 if st.get("mode")=="p_phone":
  t=normalize_phone(t); p=db.partner(t) if t else None
  if not p:return await u.message.reply_text("❌ همکار یافت نشد.",reply_markup=cancel_kb())
  st.update(phone=t,mode="p_pass"); return await u.message.reply_text("🔐 رمز عبور را وارد کنید:",reply_markup=cancel_kb())
 if st.get("mode")=="p_pass":
  p=db.partner(st.get("phone"));
  if not p or not check_password(t,p["password_hash"]):return await u.message.reply_text("❌ اطلاعات ورود نادرست است.",reply_markup=cancel_kb())
  st.update(partner_id=p["id"],mode=None); return await partner(u,c)
 if st.get("mode")=="ptrack":
  r=db.conn.execute("SELECT * FROM requests WHERE tracking_code=? AND user_id=?",(t,st["partner_id"])).fetchone(); return await u.message.reply_text(f"🎫 {r['tracking_code']}\nوضعیت: {r['status']}" if r else "❌ کد پیدا نشد.",reply_markup=partner_kb())
 return None
async def ptrack(u,c): S[u.effective_user.id]["mode"]="ptrack"; await u.message.reply_text("🎫 کد پیگیری را ارسال کنید:",reply_markup=cancel_kb())
async def phistory(u,c):
 st=S.get(u.effective_user.id,{}); rows=db.conn.execute("SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20",(st.get("partner_id",-1),)).fetchall(); await u.message.reply_text("\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,}" for r in rows) or "سابقه‌ای نیست.",reply_markup=partner_kb())
async def fida(u,c):
 uid=u.effective_user.id; S[uid]={"mode":"fida_doc","lang":S.get(uid,{}).get("lang","fa"),"partner_id":S.get(uid,{}).get("partner_id")}; await u.message.reply_text("🪪 عکس مدرک شناسایی را ارسال کنید.",reply_markup=cancel_kb())
async def gov(u,c):
 uid=u.effective_user.id; S[uid]={"mode":"gov_phone","lang":S.get(uid,{}).get("lang","fa"),"gov_files":{},"partner_id":S.get(uid,{}).get("partner_id")}; await u.message.reply_text("📱 شماره موبایل مشترک را وارد کنید.",reply_markup=cancel_kb())
async def prt(u,c):
 uid=u.effective_user.id; S[uid]={"mode":"print","files":[],"lang":S.get(uid,{}).get("lang","fa"),"partner_id":S.get(uid,{}).get("partner_id")}; await u.message.reply_text("📎 فایل‌ها را ارسال کنید؛ پایان با تأیید.",reply_markup=kb([[OK,CANCEL]]))
async def media(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{}); fid=u.message.photo[-1].file_id if u.message.photo else (u.message.document.file_id if u.message.document else "")
 if not fid:return await u.message.reply_text("❌ فایل یا تصویر معتبر ارسال کنید.",reply_markup=cancel_kb())
 if st.get("mode")=="fida_doc":
  st["doc"]=fid; st["mode"]="fida_phone"; return await u.message.reply_text("📱 شماره موبایل مشترک را وارد کنید.",reply_markup=cancel_kb())
 if st.get("mode")=="print":
  st.setdefault("files",[]).append(fid); return await u.message.reply_text(f"✅ فایل دریافت شد ({len(st['files'])}).",reply_markup=kb([[OK,CANCEL]]))
async def service_text(u,c):
 uid=u.effective_user.id; st=S.setdefault(uid,{}); t=(u.message.text or "").strip()
 if st.get("mode")=="fida_phone":
  phone=normalize_phone(t)
  if not phone:return await u.message.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789",reply_markup=cancel_kb())
  amount=int(db.setting("price_fida","0") or 0); owner=st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name); rid,code=db.create_request(owner,"fida","telegram",amount); db.answer(rid,"document",file_id=st["doc"]);db.answer(rid,"phone",phone);db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid' WHERE id=?",(rid,));db.conn.commit();st["mode"]=None;asyncio.create_task(notify_admins(c.application,f"🆕 درخواست جدید\n🎫 {code}\n🧾 فیدا\n📱 {phone}",rid));return await u.message.reply_text(f"✅ ثبت شد.\n🎫 {code}",reply_markup=partner_kb() if st.get("partner_id") else main(uid))
 if st.get("mode")=="gov_phone":
  phone=normalize_phone(t)
  if not phone:return await u.message.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789",reply_markup=cancel_kb())
  st["phone"]=phone;st["mode"]="gov_dob";return await u.message.reply_text("🎂 تاریخ تولد را به شکل 1356/01/01 وارد کنید.",reply_markup=cancel_kb())
 if st.get("mode")=="gov_dob":
  if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])",t):return await u.message.reply_text("❌ تاریخ تولد نادرست است.",reply_markup=cancel_kb())
  amount=int(db.setting("price_government","500000") or 500000);owner=st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name);rid,code=db.create_request(owner,"government","telegram",amount);db.answer(rid,"phone",st["phone"]);db.answer(rid,"dob",t);db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid' WHERE id=?",(rid,));db.conn.commit();st["mode"]=None;asyncio.create_task(notify_admins(c.application,f"🆕 درخواست جدید\n🎫 {code}\n🧾 دولت من\n📱 {st['phone']}\n🎂 {t}",rid));return await u.message.reply_text(f"✅ ثبت شد.\n🎫 {code}",reply_markup=partner_kb() if st.get("partner_id") else main(uid))
 if st.get("mode")=="print" and t==OK:
  if not st.get("files"):return await u.message.reply_text("حداقل یک فایل ارسال کنید.",reply_markup=kb([[OK,CANCEL]]))
  amount=len(st["files"])*int(db.setting("price_print_bw","0") or 0);owner=st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name);rid,code=db.create_request(owner,"print","telegram",amount)
  for i,f in enumerate(st["files"]):db.answer(rid,f"file_{i+1}",file_id=f)
  db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid' WHERE id=?",(rid,));db.conn.commit();st["mode"]=None;asyncio.create_task(notify_admins(c.application,f"🆕 درخواست جدید\n🎫 {code}\n🧾 چاپ\n📎 فایل: {len(st['files'])}",rid));return await u.message.reply_text(f"✅ ثبت شد.\n🎫 {code}",reply_markup=partner_kb() if st.get("partner_id") else main(uid))
 return None
async def admin_text(u,c):
 if not admin(u.effective_user.id):return
 t=(u.message.text or "").strip()
 if t=="👤 پنل کاربران":
  rows=db.conn.execute("SELECT id,username,full_name,platform FROM users ORDER BY id DESC LIMIT 50").fetchall();return await u.message.reply_text("👤 پنل کاربران\n\n"+"\n".join(f"{r['id']} | {r['full_name'] or '-'} | @{r['username'] or '-'}" for r in rows),reply_markup=amenu())
 if t=="👥 همکاران":
  rows=db.conn.execute("SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC").fetchall();return await u.message.reply_text("\n".join(f"#{r['id']} {r['name']} | {r['phone']} | {r['balance']:,}" for r in rows) or "همکاری نیست.",reply_markup=amenu())
 if t=="📋 درخواست‌ها":
  rows=db.conn.execute("SELECT tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 50").fetchall();return await u.message.reply_text("\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,}" for r in rows) or "درخواستی نیست.",reply_markup=amenu())
 if t=="📊 گزارش":return await u.message.reply_text(f"همکاران: {db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0]}\nدرخواست‌ها: {db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0]}",reply_markup=amenu())
 if t=="⚙️ قیمت‌ها":S[u.effective_user.id]["mode"]="price";return await u.message.reply_text("مثال: government 500000",reply_markup=cancel_kb())
 if t=="⬅️ منوی اصلی":return await u.message.reply_text("منوی اصلی",reply_markup=main(u.effective_user.id))
async def admin_cb(u,c):
 q=u.callback_query;await q.answer();
 if not admin(q.from_user.id):return
 p=q.data.split(":")
 if p[0]=="req":
  rid=int(p[2]);r=db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone();
  if not r:return
  if p[1]=="v":return await q.message.reply_text(f"🎫 {r['tracking_code']}\n🧾 {r['service_key']}\n📌 {r['status']}\n💰 {r['amount']:,} تومان",reply_markup=amenu())
  S[q.from_user.id]={"admin":True,"mode":"admin_reply_code","admin_reply_rid":rid};return await q.message.reply_text("✉️ متن پاسخ را ارسال کنید.",reply_markup=amenu())
 if p[0] in ("pay","tu"):return await q.message.reply_text("✅ عملیات مدیریت دریافت شد.",reply_markup=amenu())
async def addpartner(u,c):
 if not admin(u.effective_user.id) or len(c.args)<3:return
 try:db.add_partner(c.args[0],c.args[1]," ".join(c.args[2:]));await u.message.reply_text("همکار تعریف شد ✅")
 except:await u.message.reply_text("❌ ثبت نشد؛ شماره احتمالاً تکراری است.")
async def router(u,c):
 t=(u.message.text or "").strip();uid=u.effective_user.id
 if t in {CANCEL,"❌ Cancel","❌ إلغاء","❌ لغو","لغو","انصراف","❌ انصراف"}:return await cancel(u,c)
 if admin(uid) and S.get(uid,{}).get("mode")=="admin_reply_code":
  rid=S[uid].get("admin_reply_rid");r=db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone();usr=db.conn.execute("SELECT external_id FROM users WHERE id=?",(r["user_id"],)).fetchone() if r else None
  if usr:await c.bot.send_message(chat_id=int(usr["external_id"]),text="✉️ پاسخ مدیریت برای درخواست "+r["tracking_code"]+"\n\n"+t)
  S[uid]["mode"]=None;return await u.message.reply_text("✅ پاسخ ارسال شد.",reply_markup=amenu())
 if t==ADMIN_COMMAND:S.setdefault(uid,{})["admin"]=True;return await u.message.reply_text("🛠 پنل مدیریت",reply_markup=amenu())
 if t=="👥 پنل همکاران":return await partner(u,c)
 if t=="➕ شارژ حساب":return await u.message.reply_text("💰 شارژ فعلاً از کیف پول/مدیریت انجام می‌شود.",reply_markup=partner_kb())
 if t=="🔎 پیگیری کد":return await ptrack(u,c)
 if t=="📋 سوابق":return await phistory(u,c)
 if t=="🪪 فیدای غیر حضوری":return await fida(u,c)
 if t in ("🪪 حل مشکل ورود اتباع دولت من","🏛 حل مشکل سامانه دولت من"):return await gov(u,c)
 if t=="🖨 خدمات چاپ":return await prt(u,c)
 if t=="🛠 پنل مدیریت بات":return await u.message.reply_text("🛠 پنل مدیریت",reply_markup=amenu()) if admin(uid) else None
 if await ptext(u,c):return
 if await service_text(u,c):return
 if admin(uid):return await admin_text(u,c)
async def admin_command(u,c):S.setdefault(u.effective_user.id,{})["admin"]=True;await u.message.reply_text("🛠 پنل مدیریت",reply_markup=amenu())
def build():
 token=os.getenv("BOT_TOKEN")
 if not token:raise RuntimeError("BOT_TOKEN is missing")
 app=Application.builder().token(token).build();app.add_handler(CommandHandler("start",start));app.add_handler(CommandHandler("addpartner",addpartner));app.add_handler(MessageHandler(filters.Regex(r"^/Admin2025$"),admin_command));app.add_handler(CallbackQueryHandler(langcb,pattern=r"^lang:"));app.add_handler(CallbackQueryHandler(statuscb,pattern=r"^st:"));app.add_handler(CallbackQueryHandler(admin_cb,pattern=r"^(tu|pay|req):"));app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media));app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,router));return app
import asyncio
