import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

def parse_admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    ids = []
    for x in raw.replace(";", ",").split(","):
        x = x.strip()
        if x.isdigit() and int(x) not in ids:
            ids.append(int(x))
    return ids[:3]

ADMIN_IDS = parse_admin_ids()
DB_PATH = os.getenv("DB_PATH", "netyar.db")
DB_TIMEOUT = 30

db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=DB_TIMEOUT)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA foreign_keys=ON")

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, phone TEXT, id_code TEXT,
      city TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      platform TEXT DEFAULT 'telegram', external_id TEXT
    );
    CREATE TABLE IF NOT EXISTS services(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT '',
      price TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS service_steps(
      id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, step_no INTEGER NOT NULL,
      prompt TEXT NOT NULL, input_type TEXT DEFAULT 'text',
      FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, service_id INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY(service_id) REFERENCES services(id)
    );
    CREATE TABLE IF NOT EXISTS request_answers(
      id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL, step_id INTEGER,
      answer TEXT, file_id TEXT, created_at TEXT NOT NULL,
      FOREIGN KEY(request_id) REFERENCES requests(id)
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS buttons(key TEXT PRIMARY KEY, label TEXT NOT NULL, enabled INTEGER DEFAULT 1);
    """)
    # Safe migrations for databases created by older NetYar versions.
    for col, definition in [("platform", "TEXT DEFAULT 'telegram'"), ("external_id", "TEXT")]:
        try:
            db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    db.execute("UPDATE users SET platform='telegram' WHERE platform IS NULL OR platform=''" )
    db.execute("UPDATE users SET external_id=CAST(id AS TEXT) WHERE external_id IS NULL OR external_id=''" )

    defaults = {
      "welcome":"سلام و خوش آمدید 🌷\\nبه ربات نت‌یار خوش آمدید.",
      "support":"برای پشتیبانی با دفتر تماس بگیرید.",
      "about":"دفتر نت‌یار؛ ارائه خدمات و راهنمایی به مراجعان.",
      "announcements":"در حال حاضر اطلاعیه‌ای ثبت نشده است.",
      "maintenance":"ربات موقتاً بسته است. لطفاً بعداً دوباره تلاش کنید.",
      "bot_open":"1"
    }
    for k,v in defaults.items(): db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
    btns = {
      "register":"📝 ثبت نام", "services":"🏢 خدمات دفتر", "track":"🔎 پیگیری درخواست",
      "announcements":"📢 اطلاعیه‌ها", "support":"☎️ پشتیبانی", "about":"ℹ️ درباره ما",
      "admin":"🛠 پنل مدیریت"
    }
    for k,v in btns.items(): db.execute("INSERT OR IGNORE INTO buttons(key,label) VALUES(?,?)",(k,v))
    db.commit()

def setting(k):
    r=db.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone(); return r["value"] if r else ""

def set_setting(k,v): db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,v)); db.commit()

def button(k):
    r=db.execute("SELECT label,enabled FROM buttons WHERE key=?",(k,)).fetchone(); return (r["label"], bool(r["enabled"])) if r else (k,True)

def is_admin(uid): return uid in ADMIN_IDS

def bot_open(): return setting("bot_open") == "1"

def upsert_user(tg, platform="telegram", external_id=None, **data):
    """Create/update a user while keeping Telegram and Rubika identities in one table."""
    t=now()
    ext=str(external_id if external_id is not None else tg.id)
    username=getattr(tg, "username", "") or ""
    full_name=data.get("full_name", getattr(tg, "full_name", "") or "")
    phone=data.get("phone", "")
    id_code=data.get("id_code", "")
    city=data.get("city", "")
    r=db.execute("SELECT id FROM users WHERE platform=? AND external_id=?",(platform,ext)).fetchone()
    if r:
        db.execute("UPDATE users SET username=?,full_name=?,phone=?,id_code=?,city=?,updated_at=? WHERE id=?",
                   (username,full_name,phone,id_code,city,t,r["id"]))
        db.commit()
        return r["id"]
    # Telegram user IDs are already integers. Rubika IDs are strings, so use a stable
    # negative SQLite integer as the internal user key and keep the real Rubika ID in external_id.
    if platform == "telegram":
        internal_id=int(tg.id)
    else:
        import hashlib
        internal_id=-int(hashlib.sha256((platform+":"+ext).encode()).hexdigest()[:15],16)
        while db.execute("SELECT 1 FROM users WHERE id=?",(internal_id,)).fetchone():
            internal_id -= 1
    db.execute("INSERT INTO users(id,username,full_name,phone,id_code,city,created_at,updated_at,platform,external_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (internal_id,username,full_name,phone,id_code,city,t,t,platform,ext))
    db.commit()
    return internal_id

def main_keyboard(uid):
    keys=["register","services","track","announcements","support","about"]
    rows=[]
    enabled=[(k,button(k)[0]) for k in keys if button(k)[1]]
    for i in range(0,len(enabled),2): rows.append([x[1] for x in enabled[i:i+2]])
    if is_admin(uid): rows.append([button("admin")[0]])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
      ["📋 درخواست‌ها","🏢 خدمات و مراحل"],
      ["📊 آمار و گزارش","👥 کاربران"],
      ["✏️ ویرایش ربات","🎛 ویرایش دکمه‌ها"],
      ["🔔 اعلان مدیران","📢 پیام همگانی"],
      ["🟢 باز کردن ربات","🔴 بستن ربات"],
      ["⚙️ تنظیمات","⬅️ بازگشت"]
    ],resize_keyboard=True)

async def start(update, context):
    upsert_user(update.effective_user)
    uid=update.effective_user.id
    if not bot_open() and not is_admin(uid):
        await update.message.reply_text(setting("maintenance")); return
    await update.message.reply_text(setting("welcome").replace("\\n","\n"),reply_markup=main_keyboard(uid))
    if is_admin(uid): await update.message.reply_text("🔐 مدیر شناسایی شد. برای ورود به پنل /admin را بزنید.")

async def myid(update,context):
    uid=update.effective_user.id
    await update.message.reply_text(f"🆔 شناسه تلگرام شما: {uid}\nمدیر: {'بله ✅' if is_admin(uid) else 'خیر ❌'}\nمدیران فعال: {len(ADMIN_IDS)}/3")

async def admin(update,context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(f"⛔ دسترسی ندارید. شناسه شما: {update.effective_user.id}"); return
    await update.message.reply_text("🔐 پورتال مدیریت\nکنترل کامل محتوای ربات، خدمات، درخواست‌ها و گزارش‌ها از اینجا انجام می‌شود.",reply_markup=admin_menu())

# Registration
USER_NAME,USER_PHONE,USER_IDCODE,USER_CITY=range(4)
async def register_start(update,context):
    context.user_data.clear(); await update.message.reply_text("لطفاً نام و نام خانوادگی را وارد کنید:"); return USER_NAME
async def get_name(update,context): context.user_data["name"]=update.message.text.strip(); await update.message.reply_text("شماره موبایل را وارد کنید:"); return USER_PHONE
async def get_phone(update,context): context.user_data["phone"]=update.message.text.strip(); await update.message.reply_text("کد اتباع یا کد شناسایی را وارد کنید:"); return USER_IDCODE
async def get_id(update,context): context.user_data["id_code"]=update.message.text.strip(); await update.message.reply_text("شهر محل سکونت را وارد کنید:"); return USER_CITY
async def get_city(update,context):
    d=context.user_data; d["city"]=update.message.text.strip(); upsert_user(update.effective_user,full_name=d["name"],phone=d["phone"],id_code=d["id_code"],city=d["city"])
    await update.message.reply_text("ثبت‌نام با موفقیت انجام شد ✅",reply_markup=main_keyboard(update.effective_user.id)); return ConversationHandler.END
async def cancel(update,context): await update.message.reply_text("لغو شد.",reply_markup=main_keyboard(update.effective_user.id)); return ConversationHandler.END

# Services / requests
async def services_menu(update,context):
    rows=db.execute("SELECT * FROM services WHERE active=1 ORDER BY id").fetchall()
    if not rows: await update.message.reply_text("هنوز خدمتی تعریف نشده است."); return
    await update.message.reply_text("خدمت موردنظر را انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(r["name"],callback_data=f"svc:{r['id']}")] for r in rows]))

async def service_selected(update,context):
    q=update.callback_query; await q.answer(); sid=int(q.data.split(":")[1])
    s=db.execute("SELECT * FROM services WHERE id=? AND active=1",(sid,)).fetchone()
    if not s: await q.edit_message_text("این خدمت فعال نیست."); return
    steps=db.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no",(sid,)).fetchall()
    if not steps: await q.edit_message_text(f"🏢 {s['name']}\n{s['description']}\n💰 {s['price'] or 'اعلام نشده'}\n\nاین خدمت هنوز مرحله‌ای ندارد."); return
    cur=db.execute("INSERT INTO requests(user_id,service_id,status,created_at,updated_at) VALUES(?,?,?,?,?)",(update.effective_user.id,sid,"new",now(),now())); rid=cur.lastrowid; db.commit()
    context.user_data.update(request_id=rid,step_index=0,steps=[dict(x) for x in steps])
    await q.edit_message_text(f"درخواست #{rid} ثبت شد.\n\n{steps[0]['prompt']}"); await notify_admins(rid)

async def service_input(update,context):
    if "request_id" not in context.user_data:return
    rid=context.user_data["request_id"]; steps=context.user_data.get("steps",[]); idx=context.user_data.get("step_index",0)
    if idx>=len(steps):return
    st=steps[idx]; answer=update.message.text or ""; file_id=""
    if update.message.photo: answer="عکس ارسال شد"; file_id=update.message.photo[-1].file_id
    elif update.message.document: answer=update.message.document.file_name or "فایل ارسال شد"; file_id=update.message.document.file_id
    db.execute("INSERT INTO request_answers(request_id,step_id,answer,file_id,created_at) VALUES(?,?,?,?,?)",(rid,st["id"],answer,file_id,now())); idx+=1; context.user_data["step_index"]=idx
    if idx<len(steps): db.commit(); await update.message.reply_text(steps[idx]["prompt"]); return
    db.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?",(now(),rid)); db.commit()
    await update.message.reply_text(f"درخواست #{rid} کامل ثبت شد ✅",reply_markup=main_keyboard(update.effective_user.id)); await notify_admins(rid); context.user_data.clear()

async def notify_admins(rid):
    row=db.execute("SELECT r.*,u.full_name,u.phone,u.id_code,u.city,u.id tg_id,s.name service_name FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id WHERE r.id=?",(rid,)).fetchone()
    if not row:return
    ans=db.execute("SELECT ss.step_no,ss.prompt,ra.answer FROM request_answers ra JOIN service_steps ss ON ss.id=ra.step_id WHERE ra.request_id=? ORDER BY ss.step_no",(rid,)).fetchall()
    text=(f"🔔 درخواست #{rid}\n👤 {row['full_name']}\n📱 {row['phone']}\n🪪 {row['id_code']}\n🏙 {row['city']}\n🆔 {row['tg_id']}\n🏢 {row['service_name']}\n📌 {row['status']}\n🕒 {row['created_at']}\n")
    if ans:text+="\n📋 اطلاعات:\n"+"\n".join(f"{a['step_no']}. {a['prompt']}\n   {a['answer']}" for a in ans)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 بررسی",callback_data=f"req:{rid}")],[InlineKeyboardButton("🔄 در حال انجام",callback_data=f"status:{rid}:processing"),InlineKeyboardButton("✅ انجام شد",callback_data=f"status:{rid}:done")],[InlineKeyboardButton("❌ رد شد",callback_data=f"status:{rid}:rejected")]])
    for aid in ADMIN_IDS:
        try: await app.bot.send_message(aid,text,reply_markup=kb)
        except Exception as e: logging.warning("admin notification failed %s: %s",aid,e)

# Admin services
ADD_NAME,ADD_DESC,ADD_PRICE=10,11,12
ADD_STEP_TEXT,ADD_STEP_TYPE=20,21
EDIT_SERVICE_FIELD,EDIT_SERVICE_VALUE=30,31
EDIT_TEXT_KEY,EDIT_TEXT_VALUE=40,41
EDIT_BUTTON_KEY,EDIT_BUTTON_VALUE=50,51
REPORT_FROM,REPORT_TO=60,61
BROADCAST=70

async def admin_services(update,context):
    if not is_admin(update.effective_user.id):return
    rows=db.execute("SELECT * FROM services ORDER BY id").fetchall(); kb=[[InlineKeyboardButton(f"{'🟢' if r['active'] else '🔴'} {r['name']}",callback_data=f"svcadmin:{r['id']}")] for r in rows]; kb.append([InlineKeyboardButton("➕ افزودن خدمت",callback_data="addservice")])
    await update.message.reply_text("🏢 خدمات و مراحل:",reply_markup=InlineKeyboardMarkup(kb))
async def add_service_start(update,context):
    q=update.callback_query; await q.answer(); await q.message.reply_text("نام خدمت:"); return ADD_NAME
async def add_service_name(update,context): context.user_data["new_name"]=update.message.text.strip(); await update.message.reply_text("توضیح خدمت:"); return ADD_DESC
async def add_service_desc(update,context): context.user_data["new_desc"]=update.message.text.strip(); await update.message.reply_text("مبلغ:"); return ADD_PRICE
async def add_service_price(update,context):
    d=context.user_data; cur=db.execute("INSERT INTO services(name,description,price,active,created_at) VALUES(?,?,?,?,?)",(d["new_name"],d["new_desc"],update.message.text.strip(),1,now())); db.commit(); await update.message.reply_text("خدمت اضافه شد ✅"); return ConversationHandler.END
async def service_detail(update,context):
    q=update.callback_query; await q.answer(); sid=int(q.data.split(":")[1]); s=db.execute("SELECT * FROM services WHERE id=?",(sid,)).fetchone()
    if not s:return
    steps=db.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no",(sid,)).fetchall()
    text=f"🏢 {s['name']}\nتوضیح: {s['description']}\nمبلغ: {s['price']}\nوضعیت: {'باز' if s['active'] else 'بسته'}\n\nمراحل:\n"+"\n".join(f"{x['step_no']}. {x['prompt']} [{x['input_type']}]" for x in steps)
    kb=[[InlineKeyboardButton("✏️ ویرایش خدمت",callback_data=f"editservice:{sid}")],[InlineKeyboardButton("➕ افزودن مرحله",callback_data=f"addstep:{sid}"),InlineKeyboardButton("🔄 باز/بسته",callback_data=f"toggle:{sid}")]]
    await q.message.reply_text(text,reply_markup=InlineKeyboardMarkup(kb))
async def toggle_service(update,context):
    q=update.callback_query; await q.answer(); sid=int(q.data.split(":")[1]); db.execute("UPDATE services SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?",(sid,)); db.commit(); await q.message.reply_text("وضعیت خدمت تغییر کرد ✅")
async def add_step_start(update,context): q=update.callback_query; await q.answer(); context.user_data["sid"]=int(q.data.split(":")[1]); await q.message.reply_text("متن مرحله:"); return ADD_STEP_TEXT
async def add_step_text(update,context): context.user_data["step_prompt"]=update.message.text.strip(); await update.message.reply_text("نوع پاسخ: متن / عکس / فایل / هرچیز"); return ADD_STEP_TYPE
async def add_step_type(update,context):
    sid=context.user_data["sid"]; n=db.execute("SELECT COUNT(*) c FROM service_steps WHERE service_id=?",(sid,)).fetchone()["c"]+1; db.execute("INSERT INTO service_steps(service_id,step_no,prompt,input_type) VALUES(?,?,?,?)",(sid,n,context.user_data["step_prompt"],update.message.text.strip())); db.commit(); await update.message.reply_text("مرحله اضافه شد ✅"); return ConversationHandler.END
async def edit_service_start(update,context): q=update.callback_query; await q.answer(); context.user_data["edit_sid"]=int(q.data.split(":")[1]); await q.message.reply_text("چه چیزی؟ نام / توضیح / مبلغ"); return EDIT_SERVICE_FIELD
async def edit_service_field(update,context):
    field=update.message.text.strip(); mp={"نام":"name","توضیح":"description","مبلغ":"price"}
    if field not in mp: await update.message.reply_text("فقط نام، توضیح یا مبلغ را وارد کنید."); return EDIT_SERVICE_FIELD
    context.user_data["edit_field"]=mp[field]; await update.message.reply_text("مقدار جدید:"); return EDIT_SERVICE_VALUE
async def edit_service_value(update,context):
    db.execute(f"UPDATE services SET {context.user_data['edit_field']}=? WHERE id=?",(update.message.text.strip(),context.user_data["edit_sid"])); db.commit(); await update.message.reply_text("ویرایش شد ✅"); return ConversationHandler.END

# Requests/reports/users
async def admin_requests(update,context):
    if not is_admin(update.effective_user.id):return
    rows=db.execute("SELECT r.id,r.status,r.created_at,u.full_name,u.phone,s.name service_name FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id ORDER BY r.id DESC LIMIT 30").fetchall()
    await update.message.reply_text("📋 درخواست‌ها:\n\n"+("\n".join(f"#{r['id']} | {r['service_name']} | {r['full_name']} | {r['status']} | {r['created_at']}" for r in rows) or "درخواستی نیست."))
async def admin_users(update,context):
    if not is_admin(update.effective_user.id):return
    r=db.execute("SELECT COUNT(*) c FROM users").fetchone(); await update.message.reply_text(f"👥 کاربران: {r['c']}")
async def request_detail(update,context):
    q=update.callback_query; await q.answer(); rid=int(q.data.split(":")[1]); r=db.execute("SELECT r.*,u.full_name,u.phone,u.id_code,u.city,u.id tg_id,s.name service_name FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id WHERE r.id=?",(rid,)).fetchone()
    if not r:return
    a=db.execute("SELECT ss.prompt,ra.answer FROM request_answers ra JOIN service_steps ss ON ss.id=ra.step_id WHERE ra.request_id=? ORDER BY ss.step_no",(rid,)).fetchall()
    text=f"📋 درخواست #{rid}\n👤 {r['full_name']}\n📱 {r['phone']}\n🪪 {r['id_code']}\n🏙 {r['city']}\n🆔 {r['tg_id']}\n🏢 {r['service_name']}\n📌 {r['status']}\n🕒 {r['created_at']}\n\n"+"\n".join(f"• {x['prompt']}: {x['answer']}" for x in a)
    await q.message.reply_text(text[:4000])
async def change_status(update,context):
    q=update.callback_query; await q.answer(); _,rid,status=q.data.split(":"); rid=int(rid); labels={"processing":"در حال انجام","done":"انجام شد","rejected":"رد شد"}; db.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,now(),rid)); db.commit(); r=db.execute("SELECT user_id FROM requests WHERE id=?",(rid,)).fetchone()
    if r:
        try: await app.bot.send_message(r["user_id"],f"📌 وضعیت درخواست #{rid}: {labels[status]}")
        except Exception: pass
    await q.message.reply_text("وضعیت تغییر کرد ✅")
async def report_start(update,context): await update.message.reply_text("تاریخ شروع YYYY-MM-DD:"); return REPORT_FROM
async def report_from(update,context): context.user_data["rf"]=update.message.text.strip(); await update.message.reply_text("تاریخ پایان YYYY-MM-DD:"); return REPORT_TO
async def report_to(update,context):
    try: a=datetime.strptime(context.user_data["rf"],"%Y-%m-%d"); b=datetime.strptime(update.message.text.strip(),"%Y-%m-%d")+timedelta(days=1)
    except ValueError: await update.message.reply_text("فرمت اشتباه است."); return REPORT_TO
    rows=db.execute("SELECT r.id,r.status,r.created_at,u.full_name,u.phone,u.id_code,u.city,s.name service_name FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id WHERE r.created_at>=? AND r.created_at<? ORDER BY r.created_at",(a.strftime("%Y-%m-%d 00:00:00"),b.strftime("%Y-%m-%d 00:00:00"))).fetchall()
    text=f"📊 گزارش {a.date()} تا {(b-timedelta(days=1)).date()}\nتعداد: {len(rows)}\n\n"+"\n".join(f"#{r['id']} | {r['full_name']} | {r['phone']} | {r['id_code']} | {r['city']} | {r['service_name']} | {r['status']}" for r in rows)
    await update.message.reply_text(text[:4000]); return ConversationHandler.END

# Editable texts/buttons
TEXT_KEYS={"خوش‌آمدگویی":"welcome","پشتیبانی":"support","درباره ما":"about","اطلاعیه":"announcements","پیام بسته بودن":"maintenance"}
BUTTON_KEYS={"ثبت نام":"register","خدمات":"services","پیگیری":"track","اطلاعیه":"announcements","پشتیبانی":"support","درباره ما":"about","پنل مدیریت":"admin"}
async def edit_bot_menu(update,context):
    if not is_admin(update.effective_user.id):return
    await update.message.reply_text("✏️ برای ویرایش متن، یکی از این عنوان‌ها را بفرست:\n"+"، ".join(TEXT_KEYS)+"\n\nبعد متن جدید را می‌گیریم.")
    context.user_data["edit_mode"]="text_key"
async def edit_text_flow(update,context):
    if context.user_data.get("edit_mode")!="text_key":return False
    key=TEXT_KEYS.get(update.message.text.strip())
    if not key:return False
    context.user_data["edit_mode"]="text_value"; context.user_data["edit_key"]=key; await update.message.reply_text("متن جدید را بفرست:"); return True
async def edit_button_menu(update,context):
    if not is_admin(update.effective_user.id):return
    await update.message.reply_text("🎛 نام دکمه را بفرست:\n"+"، ".join(BUTTON_KEYS)+"\n\nبعد عنوان جدید را می‌گیریم."); context.user_data["edit_mode"]="button_key"
async def editable_flow(update,context):
    mode=context.user_data.get("edit_mode"); txt=update.message.text.strip()
    if mode=="text_key":
        key=TEXT_KEYS.get(txt)
        if key: context.user_data.update(edit_mode="text_value",edit_key=key); await update.message.reply_text("متن جدید را بفرست:"); return True
    if mode=="text_value":
        set_setting(context.user_data["edit_key"],txt); context.user_data.clear(); await update.message.reply_text("متن ربات ویرایش شد ✅"); return True
    if mode=="button_key":
        key=BUTTON_KEYS.get(txt)
        if key: context.user_data.update(edit_mode="button_value",edit_key=key); await update.message.reply_text("عنوان جدید دکمه:"); return True
    if mode=="button_value":
        db.execute("UPDATE buttons SET label=? WHERE key=?",(txt,context.user_data["edit_key"])); db.commit(); context.user_data.clear(); await update.message.reply_text("دکمه ویرایش شد ✅"); return True
    return False

async def toggle_bot(update,context,open_it):
    if not is_admin(update.effective_user.id):return
    set_setting("bot_open","1" if open_it else "0"); await update.message.reply_text("ربات باز شد 🟢" if open_it else "ربات بسته شد 🔴")

async def broadcast_start(update,context): await update.message.reply_text("متن پیام همگانی:"); return BROADCAST
async def broadcast_send(update,context):
    if not is_admin(update.effective_user.id):return ConversationHandler.END
    rows=db.execute("SELECT id FROM users").fetchall(); sent=0
    for r in rows:
        try: await app.bot.send_message(r["id"],update.message.text); sent+=1
        except Exception: pass
    await update.message.reply_text(f"برای {sent} کاربر ارسال شد."); return ConversationHandler.END

async def settings(update,context):
    if not is_admin(update.effective_user.id):return
    await update.message.reply_text(f"⚙️ تنظیمات\nمدیران: {len(ADMIN_IDS)}/3\nکاربران: {db.execute('SELECT COUNT(*) c FROM users').fetchone()['c']}\nخدمات: {db.execute('SELECT COUNT(*) c FROM services').fetchone()['c']}\nدرخواست‌ها: {db.execute('SELECT COUNT(*) c FROM requests').fetchone()['c']}\nوضعیت ربات: {'باز 🟢' if bot_open() else 'بسته 🔴'}\n\nمدیران: {', '.join(map(str,ADMIN_IDS))}")

async def menu(update,context):
    t=update.message.text
    if await editable_flow(update,context): return
    labels={k:button(k)[0] for k in ["register","services","track","announcements","support","about","admin"]}
    if t==labels["register"]: return await register_start(update,context)
    if t==labels["services"]: return await services_menu(update,context)
    if t==labels["track"]: await update.message.reply_text("کد درخواست را ارسال کنید."); return
    if t==labels["announcements"]: await update.message.reply_text(setting("announcements")); return
    if t==labels["support"]: await update.message.reply_text(setting("support")); return
    if t==labels["about"]: await update.message.reply_text(setting("about")); return
    if t==labels["admin"]: await admin(update,context); return
    if t=="📋 درخواست‌ها": await admin_requests(update,context); return
    if t=="🏢 خدمات و مراحل": await admin_services(update,context); return
    if t=="📊 آمار و گزارش": await report_start(update,context); return
    if t=="👥 کاربران": await admin_users(update,context); return
    if t=="✏️ ویرایش ربات": await edit_bot_menu(update,context); return
    if t=="🎛 ویرایش دکمه‌ها": await edit_button_menu(update,context); return
    if t=="🔔 اعلان مدیران": await update.message.reply_text(f"اعلان فوری فعال است. تعداد مدیران: {len(ADMIN_IDS)}/3"); return
    if t=="📢 پیام همگانی": return await broadcast_start(update,context)
    if t=="🟢 باز کردن ربات": await toggle_bot(update,context,True); return
    if t=="🔴 بستن ربات": await toggle_bot(update,context,False); return
    if t=="⚙️ تنظیمات": await settings(update,context); return
    if t=="⬅️ بازگشت": await update.message.reply_text("به منوی اصلی برگشتید.",reply_markup=main_keyboard(update.effective_user.id)); return
    await service_input(update,context)

async def error_handler(update,context): logging.exception("Unhandled error",exc_info=context.error)

def main():
    global app
    init_db()
    app=Application.builder().token(TOKEN).build()
    registration=ConversationHandler(entry_points=[MessageHandler(filters.Regex("^📝 ثبت نام$"),register_start)],states={USER_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_name)],USER_PHONE:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_phone)],USER_IDCODE:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_id)],USER_CITY:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_city)]},fallbacks=[CommandHandler("cancel",cancel)])
    add_service=ConversationHandler(entry_points=[CallbackQueryHandler(add_service_start,pattern="^addservice$")],states={ADD_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,add_service_name)],ADD_DESC:[MessageHandler(filters.TEXT & ~filters.COMMAND,add_service_desc)],ADD_PRICE:[MessageHandler(filters.TEXT & ~filters.COMMAND,add_service_price)]},fallbacks=[CommandHandler("cancel",cancel)],per_message=False)
    add_step=ConversationHandler(entry_points=[CallbackQueryHandler(add_step_start,pattern=r"^addstep:\d+$")],states={ADD_STEP_TEXT:[MessageHandler(filters.TEXT & ~filters.COMMAND,add_step_text)],ADD_STEP_TYPE:[MessageHandler(filters.TEXT & ~filters.COMMAND,add_step_type)]},fallbacks=[CommandHandler("cancel",cancel)],per_message=False)
    edit_service=ConversationHandler(entry_points=[CallbackQueryHandler(edit_service_start,pattern=r"^editservice:\d+$")],states={EDIT_SERVICE_FIELD:[MessageHandler(filters.TEXT & ~filters.COMMAND,edit_service_field)],EDIT_SERVICE_VALUE:[MessageHandler(filters.TEXT & ~filters.COMMAND,edit_service_value)]},fallbacks=[CommandHandler("cancel",cancel)],per_message=False)
    report=ConversationHandler(entry_points=[MessageHandler(filters.Regex("^📊 آمار و گزارش$"),report_start)],states={REPORT_FROM:[MessageHandler(filters.TEXT & ~filters.COMMAND,report_from)],REPORT_TO:[MessageHandler(filters.TEXT & ~filters.COMMAND,report_to)]},fallbacks=[CommandHandler("cancel",cancel)])
    broadcast=ConversationHandler(entry_points=[MessageHandler(filters.Regex("^📢 پیام همگانی$"),broadcast_start)],states={BROADCAST:[MessageHandler(filters.TEXT & ~filters.COMMAND,broadcast_send)]},fallbacks=[CommandHandler("cancel",cancel)])
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("admin",admin)); app.add_handler(CommandHandler("myid",myid))
    app.add_handler(registration); app.add_handler(add_service); app.add_handler(add_step); app.add_handler(edit_service); app.add_handler(report); app.add_handler(broadcast)
    app.add_handler(CallbackQueryHandler(service_selected,pattern=r"^svc:\d+$")); app.add_handler(CallbackQueryHandler(service_detail,pattern=r"^svcadmin:\d+$")); app.add_handler(CallbackQueryHandler(toggle_service,pattern=r"^toggle:\d+$")); app.add_handler(CallbackQueryHandler(request_detail,pattern=r"^req:\d+$")); app.add_handler(CallbackQueryHandler(change_status,pattern=r"^status:\d+:(processing|done|rejected)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,menu)); app.add_error_handler(error_handler)
    logging.info("NetYar v4 started. Admins=%s",ADMIN_IDS); app.run_polling()
    

if __name__=="__main__": main()
