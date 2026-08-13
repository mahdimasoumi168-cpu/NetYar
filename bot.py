import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

def parse_admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    ids = set()
    for item in raw.replace(";", ",").split(","):
        item = item.strip()
        if item.isdigit():
            ids.add(int(item))
    return ids

ADMIN_IDS = parse_admin_ids()
DB_PATH = os.getenv("DB_PATH", "netyar.db")

USER_NAME, USER_PHONE, USER_IDCODE, USER_CITY = range(4)
SERVICE_INPUT = 20
ADD_SERVICE_NAME, ADD_SERVICE_DESC, ADD_SERVICE_PRICE = range(30, 33)
ADD_STEP_TEXT, ADD_STEP_TYPE = range(40, 42)
EDIT_TEXT_VALUE = 50
REPORT_FROM, REPORT_TO = 60, 61
BROADCAST_TEXT = 70

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row

def init_db():
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        phone TEXT,
        id_code TEXT,
        city TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS service_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        prompt TEXT NOT NULL,
        input_type TEXT DEFAULT 'text',
        FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(service_id) REFERENCES services(id)
    );
    CREATE TABLE IF NOT EXISTS request_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        step_id INTEGER,
        answer TEXT,
        file_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(request_id) REFERENCES requests(id)
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    defaults = {
        "welcome": "سلام و خوش آمدید 🌷\\nبه ربات دفتر نت‌یار مهاجر خوش آمدید.",
        "support": "برای پشتیبانی با دفتر تماس بگیرید.",
        "about": "دفتر نت‌یار مهاجر؛ ارائه خدمات و راهنمایی به مراجعان."
    }
    for k, v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
    db.commit()

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def setting(key):
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else ""

def is_admin(user_id):
    return user_id in ADMIN_IDS

def upsert_user(tg_user, **data):
    t = now()
    row = db.execute("SELECT id FROM users WHERE id=?", (tg_user.id,)).fetchone()
    values = {
        "username": tg_user.username or "",
        "full_name": data.get("full_name", tg_user.full_name or ""),
        "phone": data.get("phone", ""),
        "id_code": data.get("id_code", ""),
        "city": data.get("city", "")
    }
    if row:
        db.execute("""UPDATE users SET username=?, full_name=?, phone=?, id_code=?, city=?, updated_at=?
                      WHERE id=?""",
                   (values["username"], values["full_name"], values["phone"],
                    values["id_code"], values["city"], t, tg_user.id))
    else:
        db.execute("""INSERT INTO users(id,username,full_name,phone,id_code,city,created_at,updated_at)
                      VALUES(?,?,?,?,?,?,?,?)""",
                   (tg_user.id, values["username"], values["full_name"], values["phone"],
                    values["id_code"], values["city"], t, t))
    db.commit()

def main_keyboard(user_id):
    rows = [
        ["📝 ثبت نام", "🏢 خدمات دفتر"],
        ["🔎 پیگیری درخواست", "📢 اطلاعیه‌ها"],
        ["☎️ پشتیبانی", "ℹ️ درباره ما"]
    ]
    if is_admin(user_id):
        rows.append(["🛠 پنل مدیریت"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upsert_user(update.effective_user)
    uid = update.effective_user.id
    logging.info("START from user_id=%s username=%s is_admin=%s configured_admins=%s",
                 uid, update.effective_user.username or "", is_admin(uid), sorted(ADMIN_IDS))
    await update.message.reply_text(setting("welcome"), reply_markup=main_keyboard(uid))
    if is_admin(uid):
        await update.message.reply_text(
            "🔐 شما به عنوان مدیر شناسایی شدید.\n"
            "برای ورود مستقیم به پنل، /admin را بفرستید یا دکمه «🛠 پنل مدیریت» را بزنید."
        )
    else:
        await update.message.reply_text(
            f"شناسه عددی حساب شما: {uid}\n"
            "اگر مدیر هستید ولی پنل را نمی‌بینید، همین عدد را در Railway → Variables → ADMIN_IDS قرار دهید."
        )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    logging.info("ADMIN command from user_id=%s is_admin=%s configured_admins=%s",
                 uid, is_admin(uid), sorted(ADMIN_IDS))
    if not is_admin(uid):
        await update.message.reply_text(
            f"⛔ دسترسی ندارید.\nشناسه عددی شما: {uid}\n"
            "این شناسه باید در Railway در متغیر ADMIN_IDS قرار بگیرد."
        )
        return
    await admin_panel(update, context)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        f"🆔 Telegram User ID: {uid}\n"
        f"مدیر: {'بله ✅' if is_admin(uid) else 'خیر ❌'}"
    )

async def register_start(update, context):
    context.user_data.clear()
    await update.message.reply_text("لطفاً نام و نام خانوادگی خود را وارد کنید:")
    return USER_NAME

async def get_name(update, context):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("شماره موبایل خود را وارد کنید:")
    return USER_PHONE

async def get_phone(update, context):
    context.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("کد اتباع یا کد شناسایی را وارد کنید:")
    return USER_IDCODE

async def get_id(update, context):
    context.user_data["id_code"] = update.message.text.strip()
    await update.message.reply_text("شهر محل سکونت خود را وارد کنید:")
    return USER_CITY

async def get_city(update, context):
    context.user_data["city"] = update.message.text.strip()
    upsert_user(update.effective_user, full_name=context.user_data["name"],
                phone=context.user_data["phone"], id_code=context.user_data["id_code"],
                city=context.user_data["city"])
    await update.message.reply_text(
        "ثبت‌نام اولیه شما با موفقیت انجام شد ✅\n"
        f"نام: {context.user_data['name']}\n"
        f"شهر: {context.user_data['city']}",
        reply_markup=main_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=main_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def services_menu(update, context):
    rows = db.execute("SELECT * FROM services WHERE active=1 ORDER BY id").fetchall()
    if not rows:
        await update.message.reply_text("هنوز خدمتی تعریف نشده است.")
        return
    buttons = [[InlineKeyboardButton(f"🏢 {r['name']}", callback_data=f"svc:{r['id']}")] for r in rows]
    await update.message.reply_text("خدمت موردنظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))

async def service_selected(update, context):
    q = update.callback_query
    await q.answer()
    sid = int(q.data.split(":")[1])
    service = db.execute("SELECT * FROM services WHERE id=? AND active=1", (sid,)).fetchone()
    if not service:
        await q.edit_message_text("این خدمت دیگر فعال نیست.")
        return
    steps = db.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no", (sid,)).fetchall()
    if not steps:
        await q.edit_message_text(
            f"🏢 {service['name']}\n{service['description']}\n"
            f"💰 مبلغ: {service['price'] or 'اعلام نشده'}\n\n"
            "این خدمت هنوز مرحله‌ای برای دریافت اطلاعات ندارد."
        )
        return
    req = db.execute(
        "INSERT INTO requests(user_id,service_id,status,created_at,updated_at) VALUES(?,?,?,?,?)",
        (update.effective_user.id, sid, "new", now(), now())
    )
    request_id = req.lastrowid
    db.commit()
    context.user_data["request_id"] = request_id
    context.user_data["step_index"] = 0
    context.user_data["service_id"] = sid
    context.user_data["steps"] = [dict(s) for s in steps]
    await q.edit_message_text(
        f"درخواست شما برای «{service['name']}» ثبت شد. شماره درخواست: #{request_id}\n\n"
        f"{steps[0]['prompt']}"
    )
    await notify_admins_new_request(update.effective_user.id, request_id)

async def service_input(update, context):
    if "request_id" not in context.user_data:
        return
    request_id = context.user_data["request_id"]
    steps = context.user_data.get("steps", [])
    idx = context.user_data.get("step_index", 0)
    if idx >= len(steps):
        return
    step = steps[idx]
    answer = update.message.text or ""
    file_id = ""
    if update.message.photo:
        answer = "عکس ارسال شد"
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        answer = update.message.document.file_name or "فایل ارسال شد"
        file_id = update.message.document.file_id
    db.execute(
        "INSERT INTO request_answers(request_id,step_id,answer,file_id,created_at) VALUES(?,?,?,?,?)",
        (request_id, step["id"], answer, file_id, now())
    )
    context.user_data["step_index"] = idx + 1
    if idx + 1 < len(steps):
        db.commit()
        await update.message.reply_text(steps[idx + 1]["prompt"])
        return
    db.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (now(), request_id))
    db.commit()
    await update.message.reply_text(
        f"درخواست #{request_id} کامل ثبت شد ✅\n"
        "درخواست شما برای مدیر ارسال شد و نتیجه از همین ربات اطلاع‌رسانی می‌شود.",
        reply_markup=main_keyboard(update.effective_user.id)
    )
    await notify_admins_new_request(update.effective_user.id, request_id)
    context.user_data.clear()

async def notify_admins_new_request(user_id, request_id):
    if not ADMIN_IDS:
        logging.warning("ADMIN_IDS is empty; no admin notification can be sent.")
        return
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    req = db.execute("""
        SELECT r.*, s.name service_name FROM requests r
        JOIN services s ON s.id=r.service_id WHERE r.id=?
    """, (request_id,)).fetchone()
    answers = db.execute("""
        SELECT sa.step_no, sa.prompt, ra.answer FROM request_answers ra
        JOIN service_steps sa ON sa.id=ra.step_id
        WHERE ra.request_id=? ORDER BY sa.step_no
    """, (request_id,)).fetchall()
    text = (
        f"🔔 درخواست جدید #{request_id}\n\n"
        f"👤 نام: {user['full_name']}\n"
        f"📱 موبایل: {user['phone']}\n"
        f"🪪 کد شناسایی: {user['id_code']}\n"
        f"🏙 شهر: {user['city']}\n"
        f"🆔 Telegram ID: {user['id']}\n"
        f"🏢 خدمت: {req['service_name']}\n"
        f"🕒 زمان: {req['created_at']}\n\n"
    )
    if answers:
        text += "📋 اطلاعات درخواست:\n" + "\n".join(
            f"{a['step_no']}. {a['prompt']}\n   {a['answer']}" for a in answers
        )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 بررسی", callback_data=f"req:{request_id}"),
        InlineKeyboardButton("🔄 در حال انجام", callback_data=f"status:{request_id}:processing")
    ], [
        InlineKeyboardButton("✅ انجام شد", callback_data=f"status:{request_id}:done"),
        InlineKeyboardButton("❌ رد شد", callback_data=f"status:{request_id}:rejected")
    ]])
    for aid in ADMIN_IDS:
        try:
            await app.bot.send_message(aid, text, reply_markup=kb)
        except Exception:
            logging.exception("Could not notify admin %s", aid)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["📋 درخواست‌ها", "🏢 مدیریت خدمات"],
        ["📊 گزارش آماری", "👥 کاربران"],
        ["✏️ ویرایش متن‌ها", "📢 پیام همگانی"],
        ["⚙️ تنظیمات", "⬅️ بازگشت"]
    ], resize_keyboard=True)

async def admin_panel(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    await update.message.reply_text(
        "🔐 پنل مدیریت\nهمه مدیریت‌های روزمره ربات از اینجا انجام می‌شود.",
        reply_markup=admin_menu()
    )

async def admin_requests(update, context):
    if not is_admin(update.effective_user.id): return
    rows = db.execute("""
        SELECT r.id,r.status,r.created_at,u.full_name,u.phone,s.name service_name
        FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id
        ORDER BY r.id DESC LIMIT 20
    """).fetchall()
    if not rows:
        await update.message.reply_text("درخواستی ثبت نشده است.")
        return
    text = "📋 آخرین درخواست‌ها:\n\n" + "\n".join(
        f"#{r['id']} | {r['service_name']} | {r['full_name']} | {r['status']} | {r['created_at']}"
        for r in rows
    )
    await update.message.reply_text(text)

async def admin_users(update, context):
    if not is_admin(update.effective_user.id): return
    count = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    await update.message.reply_text(f"👥 تعداد کاربران ثبت‌شده: {count}")

async def admin_services(update, context):
    if not is_admin(update.effective_user.id): return
    rows = db.execute("SELECT * FROM services ORDER BY id").fetchall()
    buttons = [[InlineKeyboardButton(f"✏️ {r['name']}", callback_data=f"svcadmin:{r['id']}")] for r in rows]
    buttons.append([InlineKeyboardButton("➕ افزودن خدمت", callback_data="addservice")])
    await update.message.reply_text("🏢 مدیریت خدمات:", reply_markup=InlineKeyboardMarkup(buttons))

async def add_service_start(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["admin_flow"] = "add_service"
    await q.message.reply_text("نام خدمت را وارد کنید:")
    return ADD_SERVICE_NAME

async def add_service_name(update, context):
    context.user_data["new_service_name"] = update.message.text.strip()
    await update.message.reply_text("توضیح خدمت را وارد کنید:")
    return ADD_SERVICE_DESC

async def add_service_desc(update, context):
    context.user_data["new_service_desc"] = update.message.text.strip()
    await update.message.reply_text("مبلغ خدمت را وارد کنید؛ اگر ندارد بنویسید «ندارد»:")
    return ADD_SERVICE_PRICE

async def add_service_price(update, context):
    d = context.user_data
    cur = db.execute(
        "INSERT INTO services(name,description,price,active,created_at) VALUES(?,?,?,?,?)",
        (d["new_service_name"], d["new_service_desc"], update.message.text.strip(), 1, now())
    )
    db.commit()
    d["editing_service"] = cur.lastrowid
    d.pop("admin_flow", None)
    await update.message.reply_text(
        f"خدمت «{d['new_service_name']}» اضافه شد ✅\n"
        "حالا از «مدیریت خدمات» می‌توانی برای آن مرحله تعریف کنی."
    )
    return ConversationHandler.END

async def service_admin_detail(update, context):
    q = update.callback_query
    await q.answer()
    sid = int(q.data.split(":")[1])
    service = db.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()
    if not service: return
    steps = db.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no", (sid,)).fetchall()
    text = (
        f"🏢 {service['name']}\n"
        f"توضیح: {service['description']}\n"
        f"مبلغ: {service['price']}\n"
        f"فعال: {'بله' if service['active'] else 'خیر'}\n\n"
        "مراحل:\n"
    )
    text += "\n".join(f"{s['step_no']}. {s['prompt']} [{s['input_type']}]" for s in steps) or "هنوز مرحله‌ای ندارد."
    kb = [
        [InlineKeyboardButton("➕ افزودن مرحله", callback_data=f"addstep:{sid}")],
        [InlineKeyboardButton("🔄 فعال/غیرفعال", callback_data=f"toggle:{sid}")]
    ]
    await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def add_step_start(update, context):
    q = update.callback_query
    await q.answer()
    sid = int(q.data.split(":")[1])
    context.user_data["editing_service"] = sid
    await q.message.reply_text("متن مرحله را وارد کنید. مثال: «رسید پرداخت را ارسال کنید.»")
    return ADD_STEP_TEXT

async def add_step_text(update, context):
    context.user_data["step_prompt"] = update.message.text.strip()
    await update.message.reply_text("نوع پاسخ را وارد کنید: متن / عکس / فایل / هرچیز")
    return ADD_STEP_TYPE

async def add_step_type(update, context):
    sid = context.user_data["editing_service"]
    typ = update.message.text.strip()
    count = db.execute("SELECT COUNT(*) c FROM service_steps WHERE service_id=?", (sid,)).fetchone()["c"]
    db.execute(
        "INSERT INTO service_steps(service_id,step_no,prompt,input_type) VALUES(?,?,?,?)",
        (sid, count + 1, context.user_data["step_prompt"], typ)
    )
    db.commit()
    await update.message.reply_text("مرحله با موفقیت اضافه شد ✅")
    context.user_data.pop("editing_service", None)
    context.user_data.pop("step_prompt", None)
    return ConversationHandler.END

async def toggle_service(update, context):
    q = update.callback_query
    await q.answer()
    sid = int(q.data.split(":")[1])
    db.execute("UPDATE services SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (sid,))
    db.commit()
    await q.message.reply_text("وضعیت خدمت تغییر کرد ✅")

async def request_detail(update, context):
    q = update.callback_query
    await q.answer()
    rid = int(q.data.split(":")[1])
    row = db.execute("""
        SELECT r.*,u.full_name,u.phone,u.id_code,u.city,u.id tg_id,s.name service_name
        FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id
        WHERE r.id=?
    """, (rid,)).fetchone()
    if not row: return
    answers = db.execute("""
        SELECT ss.prompt,ra.answer FROM request_answers ra
        JOIN service_steps ss ON ss.id=ra.step_id WHERE ra.request_id=? ORDER BY ss.step_no
    """, (rid,)).fetchall()
    text = (
        f"📋 درخواست #{rid}\n"
        f"👤 {row['full_name']}\n📱 {row['phone']}\n🪪 {row['id_code']}\n"
        f"🏙 {row['city']}\n🆔 {row['tg_id']}\n🏢 {row['service_name']}\n"
        f"📌 وضعیت: {row['status']}\n🕒 {row['created_at']}\n\n"
    )
    text += "\n".join(f"• {a['prompt']}: {a['answer']}" for a in answers)
    await q.message.reply_text(text)

async def change_status(update, context):
    q = update.callback_query
    await q.answer()
    _, rid, status = q.data.split(":")
    rid = int(rid)
    labels = {"processing":"در حال انجام","done":"انجام شد","rejected":"رد شد"}
    db.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (status, now(), rid))
    db.commit()
    req = db.execute("SELECT user_id FROM requests WHERE id=?", (rid,)).fetchone()
    if req:
        try:
            await app.bot.send_message(req["user_id"], f"📌 وضعیت درخواست #{rid} تغییر کرد:\n{labels.get(status,status)}")
        except Exception:
            logging.exception("Could not notify customer")
    await q.message.reply_text(f"وضعیت درخواست #{rid} به «{labels.get(status,status)}» تغییر کرد ✅")

async def report_start(update, context):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("تاریخ شروع را به شکل YYYY-MM-DD وارد کنید:")
    return REPORT_FROM

async def report_from(update, context):
    context.user_data["report_from"] = update.message.text.strip()
    await update.message.reply_text("تاریخ پایان را به شکل YYYY-MM-DD وارد کنید:")
    return REPORT_TO

async def report_to(update, context):
    try:
        start = datetime.strptime(context.user_data["report_from"], "%Y-%m-%d")
        end = datetime.strptime(update.message.text.strip(), "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        await update.message.reply_text("فرمت تاریخ درست نیست. مثال: 2026-08-13")
        return REPORT_TO
    rows = db.execute("""
        SELECT r.id,r.status,r.created_at,u.full_name,u.phone,u.id_code,u.city,s.name service_name
        FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id
        WHERE r.created_at >= ? AND r.created_at < ?
        ORDER BY r.created_at
    """, (start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 00:00:00"))).fetchall()
    if not rows:
        text = "برای این بازه درخواستی پیدا نشد."
    else:
        text = f"📊 گزارش {start.date()} تا {(end-timedelta(days=1)).date()}\nتعداد: {len(rows)}\n\n"
        text += "\n".join(
            f"#{r['id']} | {r['full_name']} | {r['phone']} | کد: {r['id_code']} | "
            f"{r['service_name']} | {r['status']} | {r['created_at']}" for r in rows
        )
    await update.message.reply_text(text[:4000])
    return ConversationHandler.END

async def broadcast_start(update, context):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("متن پیام همگانی را وارد کنید:")
    return BROADCAST_TEXT

async def broadcast_send(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    users = db.execute("SELECT id FROM users").fetchall()
    sent = 0
    for row in users:
        try:
            await app.bot.send_message(row["id"], update.message.text)
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"پیام برای {sent} کاربر ارسال شد.")
    return ConversationHandler.END

async def text_menu(update, context):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(
        f"✏️ متن‌های فعلی:\n\nخوش‌آمدگویی:\n{setting('welcome')}\n\nپشتیبانی:\n{setting('support')}\n\nدرباره ما:\n{setting('about')}\n\n"
        "برای ویرایش فعلاً از بخش تنظیمات پروژه استفاده می‌شود."
    )

async def menu(update, context):
    text = update.message.text
    if text == "📝 ثبت نام":
        return await register_start(update, context)
    if text == "🏢 خدمات دفتر":
        return await services_menu(update, context)
    if text == "🔎 پیگیری درخواست":
        await update.message.reply_text("کد درخواست خود را ارسال کنید.")
    elif text == "📢 اطلاعیه‌ها":
        await update.message.reply_text("در حال حاضر اطلاعیه‌ای ثبت نشده است.")
    elif text == "☎️ پشتیبانی":
        await update.message.reply_text(setting("support"))
    elif text == "ℹ️ درباره ما":
        await update.message.reply_text(setting("about"))
    elif text == "🛠 پنل مدیریت":
        await admin_panel(update, context)
    elif text == "📋 درخواست‌ها":
        await admin_requests(update, context)
    elif text == "🏢 مدیریت خدمات":
        await admin_services(update, context)
    elif text == "👥 کاربران":
        await admin_users(update, context)
    elif text == "📊 گزارش آماری":
        await report_start(update, context)
    elif text == "📢 پیام همگانی":
        await broadcast_start(update, context)
    elif text == "✏️ ویرایش متن‌ها":
        await text_menu(update, context)
    elif text == "⚙️ تنظیمات":
        await update.message.reply_text(
            "⚙️ تنظیمات\n"
            f"تعداد مدیران: {len(ADMIN_IDS)}\n"
            f"تعداد کاربران: {db.execute('SELECT COUNT(*) c FROM users').fetchone()['c']}\n"
            f"تعداد خدمات: {db.execute('SELECT COUNT(*) c FROM services').fetchone()['c']}"
        )
    elif text == "⬅️ بازگشت":
        await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=main_keyboard(update.effective_user.id))
    else:
        await service_input(update, context)

def main():
    global app
    init_db()
    app = Application.builder().token(TOKEN).build()

    registration = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 ثبت نام$"), register_start)],
        states={
            USER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            USER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            USER_IDCODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_id)],
            USER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    add_service_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_service_start, pattern="^addservice$")],
        states={
            ADD_SERVICE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_name)],
            ADD_SERVICE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_desc)],
            ADD_SERVICE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
    add_step_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_step_start, pattern=r"^addstep:\d+$")],
        states={
            ADD_STEP_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step_text)],
            ADD_STEP_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
    report_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 گزارش آماری$"), report_start)],
        states={
            REPORT_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_from)],
            REPORT_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_to)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 پیام همگانی$"), broadcast_start)],
        states={BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(registration)
    app.add_handler(add_service_conv)
    app.add_handler(add_step_conv)
    app.add_handler(report_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(CallbackQueryHandler(service_selected, pattern=r"^svc:\d+$"))
    app.add_handler(CallbackQueryHandler(service_admin_detail, pattern=r"^svcadmin:\d+$"))
    app.add_handler(CallbackQueryHandler(toggle_service, pattern=r"^toggle:\d+$"))
    app.add_handler(CallbackQueryHandler(request_detail, pattern=r"^req:\d+$"))
    app.add_handler(CallbackQueryHandler(change_status, pattern=r"^status:\d+:(processing|done|rejected)$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, service_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    logging.info("NetYar admin bot started. Admin IDs: %s", sorted(ADMIN_IDS))
    app.run_polling()

if __name__ == "__main__":
    main()
