"""Durable, database-backed configuration layer.

Operational values are stored in SQLite so routine changes do not require source
edits. This layer is deliberately additive and is loaded last.
"""
import logging, re
from core import db, now
log = logging.getLogger("netyar.admin_control_v5")
DONE=False
DEFAULT={
 "support_id":"@Good_ok_2000", "restart_text":"🔄 شروع مجدد",
 "disabled_text":"⏳ این بخش فعلاً بسته است.",
 "support_text":"📞 پشتیبانی: @Good_ok_2000",
 "welcome_fa":"سلام و خوش آمدید 🌷\nبه «کمک یار مهاجر» خوش آمدید.",
 "iranian_text":"🇮🇷 خدمات ایرانی را انتخاب کنید:",
 "foreign_text":"منوی خدمات کمک یار مهاجر 👇",
}

def ensure():
 db.conn.executescript("""
 CREATE TABLE IF NOT EXISTS admin_config(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS service_config(service_key TEXT PRIMARY KEY,group_name TEXT NOT NULL DEFAULT 'foreign',enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS admin_users(platform TEXT NOT NULL,external_id TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'admin',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,PRIMARY KEY(platform,external_id));
 """)
 for k,v in DEFAULT.items(): db.conn.execute("INSERT OR IGNORE INTO admin_config VALUES(?,?,?)",(k,v,now()))
 for r in db.conn.execute("SELECT key,active FROM services").fetchall():
  group="iranian" if str(r["key"]).startswith("iran") else "foreign"
  db.conn.execute("INSERT OR IGNORE INTO service_config VALUES(?,?,?,?)",(r["key"],group,int(r["active"]),now()))
 db.conn.commit()

def get(k,default=""):
 r=db.conn.execute("SELECT value FROM admin_config WHERE key=?",(k,)).fetchone(); return r["value"] if r else default

def put(k,v): db.conn.execute("INSERT OR REPLACE INTO admin_config VALUES(?,?,?)",(k,str(v),now())); db.conn.commit()

def set_service(key,enabled=None,price=None,name=None,group=None):
 r=db.conn.execute("SELECT * FROM services WHERE key=?",(key,)).fetchone()
 if not r: return False
 if enabled is not None: db.conn.execute("UPDATE services SET active=? WHERE key=?",(int(bool(enabled)),key))
 if price is not None: db.conn.execute("UPDATE services SET price=? WHERE key=?",(int(price),key))
 if name is not None: db.conn.execute("UPDATE services SET name=? WHERE key=?",(name,key))
 if group is None:
  x=db.conn.execute("SELECT group_name FROM service_config WHERE service_key=?",(key,)).fetchone(); group=x["group_name"] if x else "foreign"
 en=db.conn.execute("SELECT active FROM services WHERE key=?",(key,)).fetchone()["active"] if enabled is None else int(bool(enabled))
 db.conn.execute("INSERT OR REPLACE INTO service_config VALUES(?,?,?,?)",(key,group,en,now())); db.conn.commit(); return True

def service_rows():
 return db.conn.execute("SELECT s.key,s.name,s.price,s.active,COALESCE(c.group_name,'foreign') group_name FROM services s LEFT JOIN service_config c ON c.service_key=s.key ORDER BY s.id").fetchall()

def menu(B):
 return B.kb([["👥 کاربران","🤝 همکاران"],["📋 درخواست‌ها","🎫 تیکت‌ها"],["🟢/🔴 خدمات ایرانی","🟢/🔴 خدمات اتباع"],["💰 قیمت خدمات","📝 تغییر متن‌ها"],["📎 مدارک و فایل‌ها","👤 مدیران"],["🤖 پیام‌رسان‌ها","📊 گزارش‌ها"],["⚙️ تنظیمات پایه","📞 پشتیبانی"],["⬅️ منوی اصلی"]])

def services_menu(B,group):
 rows=[]
 for r in service_rows():
  if r["group_name"]!=group: continue
  rows.append([("🟢 " if r["active"] else "🔴 ")+str(r["name"])])
 rows.append(["➕ فعال/غیرفعال با کلید خدمت"]); rows.append(["⬅️ بازگشت"]); return B.kb(rows)

def texts_menu(B): return B.kb([["👋 خوش‌آمدگویی","🇮🇷 متن ایرانی"],["🇦🇫 متن اتباع","📞 پشتیبانی"],["🔄 شروع مجدد","⏳ خدمت بسته"],["⬅️ بازگشت"]])

def install():
 global DONE
 if DONE:return
 ensure()
 try:
  import bot as B
  oldL=B.L
  def L(uid,fa,en,ar):
   lang=B.S.get(uid,{}).get("lang","fa")
   key={"سلام و خوش آمدید 🌷\nبه بات «کمک یار مهاجر» خوش آمدید.":"welcome_fa"}.get(fa)
   if key and lang=="fa": return get(key,fa)
   return oldL(uid,fa,en,ar)
  B.L=L
  B.amenu=lambda:menu(B)
  old_admin=getattr(B,"admin_text",None)
  async def admin_text(u,c):
   uid=u.effective_user.id; st=B.S.setdefault(uid,{}); t=(u.message.text or "").strip(); mode=st.get("mode","")
   if not B.admin(uid): return await old_admin(u,c)
   if t in {"🛠 پنل مدیریت بات","🛠 پنل مدیریت","/Admin2025"}:
    st["mode"]="v5"; return await u.message.reply_text(get("admin_title","🛠 پنل مدیریت بات"),reply_markup=menu(B))
   if t=="🟢/🔴 خدمات ایرانی": st["mode"]="svc:iranian"; return await u.message.reply_text("🇮🇷 خدمات ایرانی\nبرای تغییر وضعیت، کلید خدمت را بفرستید؛ مثال: government",reply_markup=services_menu(B,"iranian"))
   if t=="🟢/🔴 خدمات اتباع": st["mode"]="svc:foreign"; return await u.message.reply_text("🇦🇫 خدمات اتباع\nبرای تغییر وضعیت، کلید خدمت را بفرستید؛ مثال: fida",reply_markup=services_menu(B,"foreign"))
   if mode.startswith("svc:"):
    key=t.split("|")[0].strip(); row=db.conn.execute("SELECT * FROM services WHERE key=?",(key,)).fetchone()
    if row:
     new=not bool(row["active"]); set_service(key,new); st["mode"]=mode; return await u.message.reply_text(("🟢 فعال شد: " if new else "🔴 بسته شد: ")+row["name"],reply_markup=services_menu(B,mode.split(":",1)[1]))
   if t=="💰 قیمت خدمات": st["mode"]="prices"; rows=[[f"{r['key']} | {r['price']:,} تومان"] for r in service_rows()]+[["⬅️ بازگشت"]]; return await u.message.reply_text("💰 برای تغییر قیمت، ابتدا کلید خدمت را ارسال کنید:",reply_markup=B.kb(rows))
   if mode=="prices":
    r=db.conn.execute("SELECT key,name,price FROM services WHERE key=?",(t.split("|")[0].strip(),)).fetchone()
    if r: st["price_key"]=r["key"];st["mode"]="price_value";return await u.message.reply_text(f"💰 قیمت فعلی {r['name']}: {r['price']:,} تومان\nعدد جدید را ارسال کنید:",reply_markup=B.cancel_kb())
   if mode=="price_value":
    raw=t.replace(",","").replace("٬","").replace(" ","")
    if raw.isdigit() and st.get("price_key"): set_service(st["price_key"],price=int(raw));st["mode"]="prices";return await u.message.reply_text("✅ قیمت ذخیره شد.",reply_markup=B.kb([[f"{r['key']} | {r['price']:,} تومان"] for r in service_rows()]+[["⬅️ بازگشت"]]))
   if t=="📝 تغییر متن‌ها": st["mode"]="texts";return await u.message.reply_text("📝 متن موردنظر را انتخاب کنید:",reply_markup=texts_menu(B))
   if mode=="texts":
    keys={"👋 خوش‌آمدگویی":"welcome_fa","🇮🇷 متن ایرانی":"iranian_text","🇦🇫 متن اتباع":"foreign_text","📞 پشتیبانی":"support_text","🔄 شروع مجدد":"restart_text","⏳ خدمت بسته":"disabled_text"}; k=keys.get(t)
    if k: st["text_key"]=k;st["mode"]="text_value";return await u.message.reply_text(f"📝 متن فعلی:\n{get(k)}\n\n✏️ متن جدید را کامل ارسال کنید:",reply_markup=B.cancel_kb())
   if mode=="text_value" and st.get("text_key"):
    put(st["text_key"],t);st["mode"]="texts";return await u.message.reply_text("✅ متن ذخیره شد و از این پس از تنظیم جدید استفاده می‌شود.",reply_markup=texts_menu(B))
   if t=="📞 پشتیبانی": st["mode"]="support";return await u.message.reply_text(f"📞 پشتیبانی فعلی: {get('support_id')}\nشناسه جدید را بفرستید:",reply_markup=B.cancel_kb())
   if mode=="support":
    if not re.fullmatch(r"@?[A-Za-z0-9_]{3,}",t): return await u.message.reply_text("❌ شناسه نامعتبر است.",reply_markup=B.cancel_kb())
    v=t if t.startswith("@") else "@"+t;put("support_id",v);put("support_text",f"📞 پشتیبانی: {v}");st["mode"]="v5";return await u.message.reply_text("✅ پشتیبانی تغییر کرد.",reply_markup=menu(B))
   if t=="⚙️ تنظیمات پایه":
    st["mode"]="base";return await u.message.reply_text("⚙️ تنظیمات پایه\nبرای تغییر شماره کارت یا متن بسته بودن خدمت، گزینه را انتخاب کنید:",reply_markup=B.kb([["💳 شماره کارت"],["👤 صاحب کارت"],["⏳ خدمت بسته"],["🔄 شروع مجدد"],["⬅️ بازگشت"]]))
   if mode=="base":
    km={"💳 شماره کارت":"card_number","👤 صاحب کارت":"card_owner","⏳ خدمت بسته":"disabled_text","🔄 شروع مجدد":"restart_text"};k=km.get(t)
    if k:st["base_key"]=k;st["mode"]="base_value";return await u.message.reply_text(f"مقدار فعلی:\n{get(k,db.setting(k,''))}\n\nمقدار جدید را ارسال کنید:",reply_markup=B.cancel_kb())
   if mode=="base_value" and st.get("base_key"):
    k=st["base_key"];put(k,t);db.set_setting(k,t);st["mode"]="base";return await u.message.reply_text("✅ ذخیره شد.",reply_markup=B.kb([["💳 شماره کارت"],["👤 صاحب کارت"],["⏳ خدمت بسته"],["🔄 شروع مجدد"],["⬅️ بازگشت"]]))
   if t=="👥 کاربران":
    n=db.conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"];return await u.message.reply_text(f"👥 کاربران: {n}",reply_markup=menu(B))
   if t=="🤝 همکاران":
    rs=db.conn.execute("SELECT name,phone,balance,active FROM partners ORDER BY id DESC LIMIT 50").fetchall();return await u.message.reply_text("🤝 همکاران\n"+"\n".join(f"{r['name']} | {r['phone']} | {r['balance']:,}" for r in rs),reply_markup=menu(B))
   if t=="📋 درخواست‌ها":
    rs=db.conn.execute("SELECT tracking_code,service_key,status,amount,platform FROM requests ORDER BY id DESC LIMIT 30").fetchall();return await u.message.reply_text("📋 درخواست‌ها\n"+"\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,} | {r['platform']}" for r in rs),reply_markup=menu(B))
   if t=="📊 گزارش‌ها":
    q=db.conn.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) a FROM requests").fetchone();return await u.message.reply_text(f"📊 درخواست: {q['n']}\n💰 مجموع: {q['a']:,} تومان",reply_markup=menu(B))
   if t=="🎫 تیکت‌ها": return await u.message.reply_text("🎫 مدیریت تیکت‌ها\nدرخواست‌های تیکت در جدول درخواست‌ها ثبت می‌شوند و از بخش درخواست‌ها قابل پیگیری‌اند.",reply_markup=menu(B))
   if t=="📎 مدارک و فایل‌ها": return await u.message.reply_text("📎 فایل‌ها در request_answers همراه درخواست ذخیره می‌شوند و از جزئیات درخواست قابل بررسی‌اند.",reply_markup=menu(B))
   if t=="🤖 پیام‌رسان‌ها": return await u.message.reply_text("🤖 Telegram و Rubika فعال‌اند. وضعیت و تنظیمات اتصال از متغیرهای امن Railway مدیریت می‌شود.",reply_markup=menu(B))
   if t=="👤 مدیران": return await u.message.reply_text("👤 مدیران\nبرای افزودن مدیر، از تنظیمات محیطی ADMIN_IDS استفاده کنید تا دسترسی اصلی محفوظ بماند.",reply_markup=menu(B))
   if t=="⬅️ بازگشت": st["mode"]="v5";return await u.message.reply_text("🛠 پنل مدیریت",reply_markup=menu(B))
   return await old_admin(u,c)
  B.admin_text=admin_text
 except Exception: log.exception("admin control v5 install failed")
 DONE=True
 log.info("admin control v5 installed")
