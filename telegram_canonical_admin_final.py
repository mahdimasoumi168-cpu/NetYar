"""Canonical Telegram admin UI owner and persistent night-access controls."""
import os,re,logging
from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import MessageHandler,CallbackQueryHandler,filters,ApplicationHandlerStop
log=logging.getLogger("netyar.canonical_admin")
ADMIN_IDS={"159039104","7165912028"}
ADMIN_TEXTS={"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات","پنل مدیریت","🔵 🛠 پنل مدیریت بات","🔵 🛠 پنل مدیریت"}

def _admin(B,uid):
 sid=str(uid); configured=set()
 for key in ("ADMIN_IDS","ADMIN_ID_1","ADMIN_ID_2","TELEGRAM_ADMIN_IDS"):
  configured.update(x.strip() for x in re.split(r"[;,\s]+",os.getenv(key,"")) if x.strip())
 if sid in ADMIN_IDS or sid in configured:return True
 try:return bool(B.admin(uid))
 except Exception:return False

def _bot_is_open(B):
 try:return str(B.db.setting("bot_enabled","1") or "1")=="1"
 except Exception:return True

def _night_public_open(B):
 try:return str(B.db.setting("night_public_open","0") or "0")=="1"
 except Exception:return False

def menu():
 full_label="🔴 بستن کامل ربات" if _bot_is_open(__import__("bot")) else "🟢 باز کردن کامل ربات"
 rows=[
  [("👤 کاربران","adm:users"),("👥 همکاران","adm:partners")],
  [("➕ افزودن همکار","adm:addpartner")],
  [("🌙 همکاران شب‌کار","night2:menu")],
  [("🌙 بستن ربات در شب","adm:night_off"),("☀️ باز کردن ربات در شب","adm:night_on")],
  [("📋 درخواست‌ها","adm:requests"),("💳 پرداخت‌ها","adm:payments")],
  [("💰 شارژها","adm:topups"),("⚙️ قیمت‌ها","adm:prices")],
  [("🟢 خدمات","adm:services")],
  [("📈 قیمت‌گذاری تک‌تک خدمات","adm:price_seq"),("📈 قیمت همکار خاص","adm:partner_price_seq")],
  [("🎫 تیکت/ارتباط با همکاران","adminpartner:list")],
  [("💵 افزایش شارژ","adm:creditup"),("💸 کاهش شارژ","adm:creditdown")],
  [("✏️ تغییر متن‌ها","adm:texts")],
  [("📊 گزارش کامل","adm:report"),("📣 اعلان همگانی","adm:announce")],
  [("🤖 بات‌های متصل","adm:bots"),("🧾 لاگ مدیریت","adm:logs")],
  [("⚙️ تنظیمات","adm:settings")],
  [(full_label,"adm:bot_toggle")],
  [("⬅️ منوی اصلی","adm:main")]
 ]
 return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data=d) for t,d in r] for r in rows])

def _reset(B,uid):
 st=B.S.setdefault(uid,{})
 st.update({"mode":"main","admin":True,"admin_plus_mode":None,"night_mode":None})
 return st

async def _send_menu(message):
 await message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",reply_markup=menu())

async def _entry(update,context,B):
 msg=getattr(update,"effective_message",None); user=getattr(update,"effective_user",None)
 if not msg or not user or not _admin(B,user.id) or (getattr(msg,"text","") or "").strip() not in ADMIN_TEXTS:return
 _reset(B,user.id);await _send_menu(msg);raise ApplicationHandlerStop

async def _full_toggle(update,context,B):
 q=getattr(update,"callback_query",None)
 if not q or q.data!="adm:bot_toggle":return
 if not _admin(B,q.from_user.id):await q.answer("❌ دسترسی مدیریت ندارید.",show_alert=True);raise ApplicationHandlerStop
 try:
  new=not _bot_is_open(B); value="1" if new else "0"
  B.db.set_setting("bot_enabled",value)
  try:B.db.conn.commit()
  except Exception:pass
  if _bot_is_open(B)!=new:raise RuntimeError("bot_enabled persistence mismatch")
  B._netyar_bot_enabled=new;await q.answer("تنظیم شد")
  text=("🔐 وضعیت کامل ربات\n\nوضعیت فعلی: 🟢 کاملاً باز\n\nهمه کاربران می‌توانند خدمات را دریافت کنند." if new else "🔐 وضعیت کامل ربات\n\nوضعیت فعلی: 🔴 کاملاً بسته\n\nربات برای کاربران عادی کاملاً بسته شد؛ فقط مدیریت می‌تواند دوباره آن را باز کند.")
  await q.message.reply_text(text,reply_markup=menu())
 except Exception:
  log.exception("canonical full bot toggle failed")
  try:await q.answer("ذخیره وضعیت ربات ناموفق بود.",show_alert=True);await q.message.reply_text("❌ تغییر وضعیت کامل ربات انجام نشد. وضعیت قبلی حفظ شده است.",reply_markup=menu())
  except Exception:pass
 raise ApplicationHandlerStop

async def _add_partner(update,context,B):
 q=update.callback_query
 if not q or q.data!="adm:addpartner":return
 if not _admin(B,q.from_user.id):await q.answer("❌ دسترسی مدیریت ندارید.",show_alert=True);raise ApplicationHandlerStop
 st=_reset(B,q.from_user.id);st["canonical_add_partner"]="name";await q.answer();await q.message.reply_text("➕ افزودن همکار\n\n👤 نام و نام خانوادگی همکار را وارد کنید:");raise ApplicationHandlerStop

async def _night(update,context,B):
 q=getattr(update,"callback_query",None)
 if not q or q.data not in {"adm:night_on","adm:night_off"}:return
 if not _admin(B,q.from_user.id):await q.answer("❌ دسترسی مدیریت ندارید.",show_alert=True);raise ApplicationHandlerStop
 enabled=q.data=="adm:night_on"; value="1" if enabled else "0"
 try:
  B.db.set_setting("night_shift_enabled",value);B.db.set_setting("night_public_open",value)
  try:B.db.conn.commit()
  except Exception:pass
  if str(B.db.setting("night_public_open","0") or "0")!=value:raise RuntimeError("night_public_open persistence mismatch")
  B._netyar_night_shift_enabled=enabled;B._netyar_night_public_open=enabled
  try:
   import telegram_offhours_partner_gate_v2 as G
   G.enforce_24x7(B)
  except Exception:log.exception("night gate refresh warning")
  await q.answer("🟢 دسترسی شبانه باز شد" if enabled else "🔴 دسترسی شبانه بسته شد")
  status="🟢 باز" if enabled else "🔴 بسته"
  await q.message.reply_text(f"🌙 کنترل ربات در شب\n\nوضعیت: {status}\n\n⏰ ساعت کاری روزانه: ۰۷:۰۰ تا ۱۹:۰۰.\nخارج از ساعت کاری، دسترسی عمومی فقط وقتی فعال است که «باز کردن ربات در شب» روشن باشد.\nهمکاران شب‌کار از بخش جداگانه مدیریت می‌شوند.",reply_markup=menu())
 except Exception:
  log.exception("canonical night switch failed")
  try:await q.answer("❌ ذخیره وضعیت شبانه ناموفق بود.",show_alert=True);await q.message.reply_text("❌ تغییر حالت شبانه انجام نشد. وضعیت قبلی حفظ شد.",reply_markup=menu())
  except Exception:pass
 raise ApplicationHandlerStop

def _night_kb(B):
 rows=B.db.conn.execute("SELECT id,name,phone,active FROM partners ORDER BY id DESC LIMIT 100").fetchall()
 kb=[]
 for r in rows:
  on=str(B.db.setting("night_worker:"+str(r["id"]),"0") or "0")=="1"
  kb.append([InlineKeyboardButton(("🟢 " if on else "🔴 ")+str(r["name"] or r["phone"]),callback_data="night2:toggle:"+str(r["id"]))])
 kb.append([InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")])
 return InlineKeyboardMarkup(kb)

async def _night_workers(update,context,B):
 q=getattr(update,"callback_query",None); data=str(getattr(q,"data","") or "")
 if not q or not data.startswith("night2:"):return
 if not _admin(B,q.from_user.id):await q.answer("❌ دسترسی مدیریت ندارید.",show_alert=True);raise ApplicationHandlerStop
 if data=="night2:menu":
  await q.answer();await q.message.reply_text("🌙 مدیریت همکاران شب‌کار\n\n🟢 فعال = اجازه کار خارج از ساعت کاری\n🔴 غیرفعال = بدون اجازه شبانه\n\nبرای تغییر روی نام همکار بزنید:",reply_markup=_night_kb(B));raise ApplicationHandlerStop
 try:pid=int(data.rsplit(":",1)[1])
 except Exception:await q.answer("شناسه همکار نامعتبر است.",show_alert=True);raise ApplicationHandlerStop
 row=B.db.conn.execute("SELECT id,name,phone,active FROM partners WHERE id=? LIMIT 1",(pid,)).fetchone()
 if not row:await q.answer("همکار پیدا نشد.",show_alert=True);raise ApplicationHandlerStop
 key="night_worker:"+str(pid);old=str(B.db.setting(key,"0") or "0")=="1";new=not old
 B.db.set_setting(key,"1" if new else "0")
 try:B.db.conn.commit()
 except Exception:pass
 if (str(B.db.setting(key,"0") or "0")=="1") != new:
  await q.answer("❌ ذخیره وضعیت همکار انجام نشد.",show_alert=True)
  raise ApplicationHandlerStop
 await q.answer("🟢 فعال شد" if new else "🔴 غیرفعال شد")
 await q.message.reply_text("🌙 وضعیت همکاران شب‌کار به‌روزرسانی شد.",reply_markup=_night_kb(B))
 raise ApplicationHandlerStop

async def _text(update,context,B):
 msg=getattr(update,"effective_message",None);user=getattr(update,"effective_user",None)
 if not msg or not user or not _admin(B,user.id):return
 t=(getattr(msg,"text","") or "").strip()
 if t in ADMIN_TEXTS:_reset(B,user.id);await _send_menu(msg);raise ApplicationHandlerStop
 st=B.S.setdefault(user.id,{})
 if st.get("canonical_add_partner"):
  mode=st["canonical_add_partner"]
  if t in {"❌ انصراف","لغو","انصراف"}:st.pop("canonical_add_partner",None);await msg.reply_text("❌ عملیات لغو شد.",reply_markup=menu());raise ApplicationHandlerStop
  if mode=="name":
   if len(t)<2:await msg.reply_text("❌ نام معتبر وارد کنید.");raise ApplicationHandlerStop
   st["canonical_partner_name"]=t;st["canonical_add_partner"]="phone";await msg.reply_text("📱 شماره موبایل همکار را وارد کنید:");raise ApplicationHandlerStop
  if mode=="phone":
   phone=re.sub(r"\D","",t).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
   if phone.startswith("98"):phone="0"+phone[2:]
   if not re.fullmatch(r"09\d{9}",phone):await msg.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.");raise ApplicationHandlerStop
   if B.db.conn.execute("SELECT 1 FROM partners WHERE phone=?",(phone,)).fetchone():await msg.reply_text("❌ این شماره قبلاً به عنوان همکار ثبت شده است.");raise ApplicationHandlerStop
   st["canonical_partner_phone"]=phone;st["canonical_add_partner"]="password";await msg.reply_text("🔐 رمز ورود همکار را وارد کنید (حداقل ۴ کاراکتر):");raise ApplicationHandlerStop
  if mode=="password":
   if len(t)<4:await msg.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.");raise ApplicationHandlerStop
   from core import hash_password
   now=B.now()
   B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(st["canonical_partner_phone"],hash_password(t),st["canonical_partner_name"],1,0,now,now));B.db.conn.commit()
   phone=st["canonical_partner_phone"];name=st["canonical_partner_name"];row=B.db.conn.execute("SELECT id FROM partners WHERE phone=?",(phone,)).fetchone()
   for k in ("canonical_add_partner","canonical_partner_name","canonical_partner_phone"):st.pop(k,None)
   await msg.reply_text(f"✅ همکار با موفقیت اضافه شد.\n\n👤 {name}\n📱 {phone}\n🆔 شناسه: {row['id'] if row else '-'}\n💰 موجودی اولیه: 0 تومان",reply_markup=menu());raise ApplicationHandlerStop
 if st.get("admin_plus_mode"):
  try:
   import telegram_admin_plus as A;r=A._text(update,context,B)
   if hasattr(r,"__await__"):await r
  except Exception:await msg.reply_text("❌ ورود اطلاعات با خطا مواجه شد. دوباره تلاش کنید.",reply_markup=menu())
  raise ApplicationHandlerStop

def install(app,B):
 B.amenu=menu;B.admin_menu_final=menu
 try:
  import telegram_admin_plus as A;A._admin_menu=menu
 except Exception:pass
 if getattr(B,"_canonical_admin_final_v9",False):return True
 app.add_handler(CallbackQueryHandler(lambda u,c:_full_toggle(u,c,B),pattern=r"^adm:bot_toggle$"),group=-100000005)
 app.add_handler(CallbackQueryHandler(lambda u,c:_add_partner(u,c,B),pattern=r"^adm:addpartner$"),group=-100000004)
 app.add_handler(CallbackQueryHandler(lambda u,c:_night(u,c,B),pattern=r"^adm:night_(on|off)$"),group=-100000003)
 app.add_handler(CallbackQueryHandler(lambda u,c:_night_workers(u,c,B),pattern=r"^night2:"),group=-100000002)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_text(u,c,B)),group=-100000000)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_entry(u,c,B)),group=-100000007)
 B._canonical_admin_final_v9=True
 log.info("Canonical admin owner active: telegram_canonical_admin_final.menu")
 return True
