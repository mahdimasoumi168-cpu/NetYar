import os
import logging
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler,
    CallbackQueryHandler, filters
)

logging.basicConfig(level=logging.INFO)
DB_PATH = Path(os.getenv('DB_PATH', 'netyar.db'))
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()}

# User registration states
REG_NAME, REG_PHONE, REG_ID, REG_CITY = range(4)
# Service request states
REQ_STEP = 10
# Admin states
A_ADD_NAME, A_EDIT_SERVICE, A_ADD_STEP_NAME, A_ADD_STEP_TYPE, A_ADD_STEP_PROMPT = range(20, 25)
A_REPORT_FROM, A_REPORT_TO = range(30, 32)
A_BROADCAST = 40

STEP_TYPES = {
    'text': 'متن',
    'photo': 'عکس',
    'document': 'فایل',
    'phone': 'شماره تماس',
    'receipt': 'رسید پرداخت',
}

MAIN_MENU = [
    ['📝 ثبت نام', '🏢 خدمات دفتر'],
    ['🔎 پیگیری درخواست', '📢 اطلاعیه‌ها'],
    ['☎️ پشتیبانی', 'ℹ️ درباره ما'],
]


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            id_code TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            payment_amount TEXT DEFAULT '',
            payment_card TEXT DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS service_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            title TEXT NOT NULL,
            step_type TEXT NOT NULL,
            prompt TEXT NOT NULL,
            FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'در انتظار بررسی',
            current_step INTEGER NOT NULL DEFAULT 0,
            data_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(service_id) REFERENCES services(id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        ''')
        defaults = {
            'welcome_text': 'سلام و خوش آمدید 🌷\nبه ربات دفتر نت‌یار مهاجر خوش آمدید.',
            'about_text': 'دفتر نت‌یار مهاجر؛ ارائه خدمات و راهنمایی به مراجعان.',
            'support_text': 'برای پشتیبانی با دفتر تماس بگیرید.',
        }
        for k, v in defaults.items():
            con.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (k, v))


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def setting(key, default=''):
    with db() as con:
        row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with db() as con:
        con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))


def is_admin(update: Update):
    uid = update.effective_user.id if update.effective_user else None
    return uid in ADMIN_IDS


def get_or_create_user(tg_user):
    t = now()
    with db() as con:
        con.execute('''INSERT INTO users(telegram_id,created_at,updated_at) VALUES(?,?,?)
                       ON CONFLICT(telegram_id) DO UPDATE SET updated_at=excluded.updated_at''', (tg_user.id, t, t))
        return con.execute('SELECT * FROM users WHERE telegram_id=?', (tg_user.id,)).fetchone()


def update_user(tg_id, **fields):
    fields['updated_at'] = now()
    keys = list(fields.keys())
    vals = [fields[k] for k in keys]
    with db() as con:
        con.execute(f"UPDATE users SET {', '.join(k+'=?' for k in keys)} WHERE telegram_id=?", vals + [tg_id])


def fmt_user(row):
    return f"نام: {row['name']}\nشماره: {row['phone']}\nکد شناسایی: {row['id_code']}\nشهر: {row['city']}\nتلگرام: {row['telegram_id']}"


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📋 درخواست‌ها', callback_data='adm:reqs')],
        [InlineKeyboardButton('🛠 خدمات', callback_data='adm:services')],
        [InlineKeyboardButton('👥 کاربران', callback_data='adm:users')],
        [InlineKeyboardButton('📊 گزارش آماری', callback_data='adm:report')],
        [InlineKeyboardButton('📢 پیام همگانی', callback_data='adm:broadcast')],
        [InlineKeyboardButton('⚙️ تنظیمات متن‌ها', callback_data='adm:settings')],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_or_create_user(update.effective_user)
    await update.message.reply_text(setting('welcome_text'), reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True))


async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_or_create_user(update.effective_user)
    await update.message.reply_text('لطفاً نام و نام خانوادگی خود را وارد کنید:')
    return REG_NAME


async def reg_name(update, context):
    context.user_data['reg_name'] = update.message.text.strip()
    kb = [[KeyboardButton('📱 ارسال شماره موبایل', request_contact=True)]]
    await update.message.reply_text('شماره موبایل خود را ارسال کنید:', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return REG_PHONE


async def reg_phone(update, context):
    phone = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    context.user_data['reg_phone'] = phone
    await update.message.reply_text('کد اتباع یا کد شناسایی را وارد کنید:')
    return REG_ID


async def reg_id(update, context):
    context.user_data['reg_id'] = update.message.text.strip()
    await update.message.reply_text('شهر محل سکونت خود را وارد کنید:')
    return REG_CITY


async def reg_city(update, context):
    update_user(update.effective_user.id, name=context.user_data['reg_name'], phone=context.user_data['reg_phone'], id_code=context.user_data['reg_id'], city=update.message.text.strip())
    await update.message.reply_text('اطلاعات شما با موفقیت ذخیره شد ✅', reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True))
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text('عملیات لغو شد.')
    return ConversationHandler.END


async def service_list(update, context):
    with db() as con:
        rows = con.execute('SELECT * FROM services WHERE enabled=1 ORDER BY id').fetchall()
    if not rows:
        await update.message.reply_text('هنوز خدمتی تعریف نشده است.')
        return
    buttons = [[InlineKeyboardButton(r['name'], callback_data=f"svc:{r['id']}")] for r in rows]
    await update.message.reply_text('خدمت موردنظر را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(buttons))


async def service_select(update, context):
    q = update.callback_query
    await q.answer()
    sid = int(q.data.split(':')[1])
    with db() as con:
        svc = con.execute('SELECT * FROM services WHERE id=? AND enabled=1', (sid,)).fetchone()
    if not svc:
        await q.edit_message_text('این خدمت در دسترس نیست.')
        return
    context.user_data['service_id'] = sid
    context.user_data['req_data'] = {}
    with db() as con:
        first = con.execute('SELECT * FROM service_steps WHERE service_id=? ORDER BY position LIMIT 1', (sid,)).fetchone()
    if svc['description']:
        text = svc['description'] + '\n\n'
    else:
        text = ''
    if svc['payment_amount']:
        text += f"💳 مبلغ: {svc['payment_amount']}\n"
    if svc['payment_card']:
        text += f"💳 شماره کارت: {svc['payment_card']}\n"
    if first:
        context.user_data['req_step_pos'] = 0
        text += f"\nمرحله ۱ — {first['prompt']}"
        await q.edit_message_text(text)
    else:
        rid = create_request(update.effective_user.id, sid, {})
        await q.edit_message_text(f'درخواست شما ثبت شد ✅\nکد درخواست: #{rid}')
        await notify_admins(context, rid)
        context.user_data.clear()


def create_request(tg_id, sid, data):
    with db() as con:
        user = con.execute('SELECT id FROM users WHERE telegram_id=?', (tg_id,)).fetchone()
        ts = now()
        cur = con.execute('INSERT INTO requests(user_id,service_id,data_json,created_at,updated_at) VALUES(?,?,?,?,?)', (user['id'], sid, json.dumps(data, ensure_ascii=False), ts, ts))
        return cur.lastrowid


def get_request(rid):
    with db() as con:
        return con.execute('''SELECT r.*, s.name service_name, u.telegram_id, u.name user_name, u.phone, u.id_code, u.city
                             FROM requests r JOIN services s ON s.id=r.service_id JOIN users u ON u.id=r.user_id WHERE r.id=?''', (rid,)).fetchone()


async def request_step_handler(update, context):
    sid = context.user_data.get('service_id')
    if not sid:
        return
    pos = context.user_data.get('req_step_pos', 0)
    with db() as con:
        steps = con.execute('SELECT * FROM service_steps WHERE service_id=? ORDER BY position', (sid,)).fetchall()
    if pos >= len(steps):
        return
    step = steps[pos]
    accepted = False
    value = None
    if step['step_type'] == 'text' and update.message.text:
        accepted, value = True, update.message.text
    elif step['step_type'] == 'phone':
        if update.message.contact:
            accepted, value = True, update.message.contact.phone_number
        elif update.message.text:
            accepted, value = True, update.message.text
    elif step['step_type'] == 'photo' and update.message.photo:
        accepted, value = True, update.message.photo[-1].file_id
    elif step['step_type'] in ('document','receipt') and update.message.document:
        accepted, value = True, update.message.document.file_id
    if not accepted:
        await update.message.reply_text(f"لطفاً پاسخ را به صورت «{STEP_TYPES[step['step_type']]}» ارسال کنید.")
        return
    context.user_data['req_data'][step['title']] = {'type': step['step_type'], 'value': value}
    pos += 1
    if pos < len(steps):
        context.user_data['req_step_pos'] = pos
        nxt = steps[pos]
        if nxt['step_type'] == 'receipt':
            await update.message.reply_text(nxt['prompt'] + '\nرسید را به‌صورت فایل ارسال کنید.')
        else:
            await update.message.reply_text(nxt['prompt'])
        return
    rid = create_request(update.effective_user.id, sid, context.user_data['req_data'])
    await update.message.reply_text(f'درخواست شما ثبت شد ✅\nکد درخواست: #{rid}')
    await notify_admins(context, rid)
    context.user_data.pop('service_id', None)
    context.user_data.pop('req_step_pos', None)
    context.user_data.pop('req_data', None)


async def notify_admins(context, rid):
    if not ADMIN_IDS:
        logging.warning('ADMIN_IDS is empty; request notification skipped.')
        return
    r = get_request(rid)
    text = (f"🔔 درخواست جدید #{rid}\n\nخدمت: {r['service_name']}\n"
            f"مشتری: {r['user_name']}\nشماره: {r['phone']}\nکد: {r['id_code']}\nشهر: {r['city']}\n"
            f"تاریخ: {r['created_at']}\nوضعیت: {r['status']}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton('🔎 مشاهده', callback_data=f'reqview:{rid}')]])
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid, text, reply_markup=kb)
        except Exception:
            logging.exception('Failed to notify admin %s', aid)


async def track_request(update, context):
    await update.message.reply_text('کد درخواست را مثل ۱۲۳ وارد کنید:')
    context.user_data['tracking'] = True


async def tracking_handler(update, context):
    if not context.user_data.pop('tracking', False):
        return False
    try:
        rid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text('کد درخواست نامعتبر است.')
        return True
    r = get_request(rid)
    if not r or r['telegram_id'] != update.effective_user.id:
        await update.message.reply_text('درخواستی با این کد برای شما پیدا نشد.')
        return True
    await update.message.reply_text(f"درخواست #{rid}\nخدمت: {r['service_name']}\nوضعیت: {r['status']}\nتاریخ: {r['created_at']}")
    return True


async def admin(update, context):
    if not is_admin(update):
        await update.message.reply_text('دسترسی مجاز نیست.')
        return
    await update.message.reply_text('پنل مدیریت نت‌یار مهاجر', reply_markup=admin_menu())


async def admin_callback(update, context):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in ADMIN_IDS:
        await q.answer('دسترسی ندارید.', show_alert=True)
        return
    data = q.data
    if data == 'adm:reqs':
        with db() as con:
            rows = con.execute('''SELECT r.id,r.status,r.created_at,s.name service_name,u.name user_name
                                  FROM requests r JOIN services s ON s.id=r.service_id JOIN users u ON u.id=r.user_id
                                  ORDER BY r.id DESC LIMIT 15''').fetchall()
        if not rows:
            await q.edit_message_text('درخواستی ثبت نشده است.', reply_markup=admin_menu())
            return
        buttons = [[InlineKeyboardButton(f"#{r['id']} | {r['service_name']} | {r['status']}", callback_data=f'reqview:{r["id"]}')] for r in rows]
        buttons.append([InlineKeyboardButton('⬅️ بازگشت', callback_data='adm:home')])
        await q.edit_message_text('آخرین درخواست‌ها:', reply_markup=InlineKeyboardMarkup(buttons))
    elif data == 'adm:services':
        with db() as con:
            rows = con.execute('SELECT * FROM services ORDER BY id').fetchall()
        buttons = [[InlineKeyboardButton(f"{'✅' if r['enabled'] else '⛔'} {r['name']}", callback_data=f'svadmin:{r["id"]}')] for r in rows]
        buttons.append([InlineKeyboardButton('➕ افزودن خدمت', callback_data='svadd')])
        buttons.append([InlineKeyboardButton('⬅️ بازگشت', callback_data='adm:home')])
        await q.edit_message_text('مدیریت خدمات:', reply_markup=InlineKeyboardMarkup(buttons))
    elif data == 'adm:users':
        with db() as con:
            count = con.execute('SELECT COUNT(*) c FROM users').fetchone()['c']
            rows = con.execute('SELECT * FROM users ORDER BY id DESC LIMIT 10').fetchall()
        text = f'تعداد کاربران: {count}\n\n' + '\n\n'.join([f"#{r['id']} {fmt_user(r)}" for r in rows])
        await q.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ بازگشت', callback_data='adm:home')]]))
    elif data == 'adm:report':
        context.user_data['admin_report'] = 'from'
        await q.edit_message_text('تاریخ شروع را به صورت YYYY-MM-DD وارد کنید:')
    elif data == 'adm:broadcast':
        context.user_data['admin_broadcast'] = True
        await q.edit_message_text('متن پیام همگانی را ارسال کنید:')
    elif data == 'adm:settings':
        context.user_data['admin_settings'] = True
        await q.edit_message_text('برای تغییر متن‌ها یکی را بنویسید:\nwelcome=متن\nabout=متن\nsupport=متن')
    elif data == 'adm:home':
        await q.edit_message_text('پنل مدیریت', reply_markup=admin_menu())
    elif data.startswith('reqview:'):
        rid = int(data.split(':')[1])
        r = get_request(rid)
        if not r:
            return
        text = (f"درخواست #{rid}\nخدمت: {r['service_name']}\nوضعیت: {r['status']}\n\n"
                f"{fmt_user(r)}\n\nتاریخ: {r['created_at']}\nاطلاعات درخواست:\n{r['data_json'][:1500]}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('🔍 در حال بررسی', callback_data=f'reqstatus:{rid}:در حال بررسی')],
            [InlineKeyboardButton('⚙️ در حال انجام', callback_data=f'reqstatus:{rid}:در حال انجام')],
            [InlineKeyboardButton('✅ انجام شد', callback_data=f'reqstatus:{rid}:انجام شد'), InlineKeyboardButton('❌ رد شد', callback_data=f'reqstatus:{rid}:رد شد')],
            [InlineKeyboardButton('⬅️ درخواست‌ها', callback_data='adm:reqs')]
        ])
        await q.edit_message_text(text, reply_markup=kb)
    elif data.startswith('reqstatus:'):
        _, rid, status = data.split(':', 2)
        rid = int(rid)
        with db() as con:
            r = con.execute('SELECT user_id, status FROM requests WHERE id=?', (rid,)).fetchone()
            con.execute('UPDATE requests SET status=?, updated_at=? WHERE id=?', (status, now(), rid))
            user = con.execute('SELECT telegram_id FROM users WHERE id=?', (r['user_id'],)).fetchone()
        await context.bot.send_message(user['telegram_id'], f'وضعیت درخواست #{rid} به «{status}» تغییر کرد.')
        await q.answer('وضعیت تغییر کرد.')
        await q.edit_message_text(f'درخواست #{rid} → {status}', reply_markup=admin_menu())
    elif data.startswith('svadmin:'):
        sid = int(data.split(':')[1])
        with db() as con:
            s = con.execute('SELECT * FROM services WHERE id=?', (sid,)).fetchone()
            steps = con.execute('SELECT * FROM service_steps WHERE service_id=? ORDER BY position', (sid,)).fetchall()
        text = f"خدمت: {s['name']}\nتوضیح: {s['description']}\nمبلغ: {s['payment_amount']}\nکارت: {s['payment_card']}\nفعال: {'بله' if s['enabled'] else 'خیر'}\n\nمراحل:\n"
        text += '\n'.join([f"{i+1}. {x['title']} [{STEP_TYPES.get(x['step_type'], x['step_type'])}]" for i,x in enumerate(steps)]) or 'بدون مرحله'
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('➕ افزودن مرحله', callback_data=f'svaddstep:{sid}')],
            [InlineKeyboardButton('🟢/🔴 تغییر وضعیت', callback_data=f'svtoggle:{sid}')],
            [InlineKeyboardButton('🗑 حذف خدمت', callback_data=f'svdel:{sid}')],
            [InlineKeyboardButton('⬅️ خدمات', callback_data='adm:services')]
        ])
        await q.edit_message_text(text[:4000], reply_markup=kb)
    elif data == 'svadd':
        context.user_data['svadd'] = True
        await q.edit_message_text('نام خدمت جدید را ارسال کنید:')
    elif data.startswith('svaddstep:'):
        sid = int(data.split(':')[1])
        context.user_data['addstep_service'] = sid
        await q.edit_message_text('عنوان مرحله را ارسال کنید:')
        context.user_data['addstep_state'] = 'title'
    elif data.startswith('svtoggle:'):
        sid = int(data.split(':')[1])
        with db() as con:
            row = con.execute('SELECT enabled FROM services WHERE id=?', (sid,)).fetchone()
            con.execute('UPDATE services SET enabled=?,updated_at=? WHERE id=?', (0 if row['enabled'] else 1, now(), sid))
        await q.edit_message_text('انجام شد ✅', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ خدمات', callback_data='adm:services')]]))
    elif data.startswith('svdel:'):
        sid = int(data.split(':')[1])
        with db() as con:
            con.execute('DELETE FROM services WHERE id=?', (sid,))
        await q.edit_message_text('خدمت حذف شد ✅', reply_markup=admin_menu())


async def admin_text_router(update, context):
    if not is_admin(update):
        return False
    text = (update.message.text or '').strip()
    if context.user_data.get('admin_report') == 'from':
        context.user_data['report_from'] = text
        context.user_data['admin_report'] = 'to'
        await update.message.reply_text('تاریخ پایان را به صورت YYYY-MM-DD وارد کنید:')
        return True
    if context.user_data.get('admin_report') == 'to':
        start = context.user_data.pop('report_from')
        context.user_data.pop('admin_report', None)
        end = text + ' 23:59:59'
        try:
            datetime.strptime(start, '%Y-%m-%d')
            datetime.strptime(text, '%Y-%m-%d')
        except ValueError:
            await update.message.reply_text('فرمت تاریخ نادرست است. مثال: 2026-08-01')
            return True
        with db() as con:
            rows = con.execute('''SELECT r.id,r.created_at,r.status,s.name service_name,u.name,u.phone,u.id_code,u.city
                                  FROM requests r JOIN services s ON s.id=r.service_id JOIN users u ON u.id=r.user_id
                                  WHERE r.created_at BETWEEN ? AND ? ORDER BY r.created_at''', (start+' 00:00:00', end)).fetchall()
        text_out = f'گزارش {start} تا {text}\nتعداد درخواست: {len(rows)}\n\n'
        text_out += '\n\n'.join([f"#{r['id']} | {r['created_at']}\nخدمت: {r['service_name']}\nنام: {r['name']}\nشماره: {r['phone']}\nکد: {r['id_code']}\nشهر: {r['city']}\nوضعیت: {r['status']}" for r in rows])
        await update.message.reply_text(text_out[:4000] if text_out else 'رکوردی پیدا نشد.')
        return True
    if context.user_data.get('admin_broadcast'):
        context.user_data.pop('admin_broadcast', None)
        with db() as con:
            ids = [r['telegram_id'] for r in con.execute('SELECT telegram_id FROM users').fetchall()]
        sent = 0
        for uid in ids:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f'پیام برای {sent} کاربر ارسال شد.')
        return True
    if context.user_data.get('admin_settings'):
        context.user_data.pop('admin_settings', None)
        if '=' not in text:
            await update.message.reply_text('فرمت باید key=متن باشد.')
            return True
        k, v = text.split('=',1)
        mapping = {'welcome':'welcome_text','about':'about_text','support':'support_text'}
        if k not in mapping:
            await update.message.reply_text('کلید نامعتبر است.')
            return True
        set_setting(mapping[k], v)
        await update.message.reply_text('متن ذخیره شد ✅')
        return True
    if context.user_data.get('svadd'):
        context.user_data.pop('svadd', None)
        with db() as con:
            cur = con.execute('INSERT INTO services(name,created_at,updated_at) VALUES(?,?,?)', (text,now(),now()))
            sid = cur.lastrowid
        await update.message.reply_text(f'خدمت «{text}» ساخته شد. حالا از پنل مدیریت، مرحله‌هایش را اضافه کن. /admin')
        return True
    if context.user_data.get('addstep_state') == 'title':
        context.user_data['addstep_title'] = text
        context.user_data['addstep_state'] = 'type'
        buttons = [[InlineKeyboardButton(label, callback_data=f'steptype:{key}') for key,label in STEP_TYPES.items()]]
        await update.message.reply_text('نوع مرحله را انتخاب کنید:', reply_markup=InlineKeyboardMarkup(buttons))
        return True
    return False


async def step_type_callback(update, context):
    q = update.callback_query
    await q.answer()
    if q.from_user.id not in ADMIN_IDS:
        return
    typ = q.data.split(':',1)[1]
    context.user_data['addstep_type'] = typ
    context.user_data['addstep_state'] = 'prompt'
    await q.edit_message_text('متن راهنمای این مرحله را ارسال کنید:')


async def admin_prompt_handler(update, context):
    if not is_admin(update):
        return False
    if context.user_data.get('addstep_state') != 'prompt':
        return False
    sid = context.user_data['addstep_service']
    title = context.user_data['addstep_title']
    typ = context.user_data['addstep_type']
    prompt = update.message.text.strip()
    with db() as con:
        pos = con.execute('SELECT COALESCE(MAX(position), -1)+1 p FROM service_steps WHERE service_id=?', (sid,)).fetchone()['p']
        con.execute('INSERT INTO service_steps(service_id,position,title,step_type,prompt) VALUES(?,?,?,?,?)', (sid,pos,title,typ,prompt))
    for k in ['addstep_service','addstep_title','addstep_type','addstep_state']:
        context.user_data.pop(k, None)
    await update.message.reply_text('مرحله اضافه شد ✅\nبرای ادامه /admin را بزن.')
    return True


async def admin_command_router(update, context):
    if await admin_prompt_handler(update, context):
        return
    if await admin_text_router(update, context):
        return


async def normal_router(update, context):
    if context.user_data.get('service_id'):
        await request_step_handler(update, context)
        return
    if await tracking_handler(update, context):
        return
    text = update.message.text
    if text == '📝 ثبت نام':
        await register_start(update, context)
    elif text == '🏢 خدمات دفتر':
        await service_list(update, context)
    elif text == '🔎 پیگیری درخواست':
        await track_request(update, context)
    elif text == '📢 اطلاعیه‌ها':
        await update.message.reply_text('در حال حاضر اطلاعیه‌ای ثبت نشده است.')
    elif text == '☎️ پشتیبانی':
        await update.message.reply_text(setting('support_text'))
    elif text == 'ℹ️ درباره ما':
        await update.message.reply_text(setting('about_text'))


def main():
    init_db()
    if not os.getenv('BOT_TOKEN'):
        raise RuntimeError('BOT_TOKEN environment variable is missing.')
    if not ADMIN_IDS:
        logging.warning('ADMIN_IDS is empty. Set it in Railway Variables, e.g. ADMIN_IDS=123456789')
    app = Application.builder().token(os.environ['BOT_TOKEN']).build()

    registration = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📝 ثبت نام$'), register_start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, reg_phone)],
            REG_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_id)],
            REG_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_city)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin))
    app.add_handler(registration)
    app.add_handler(CallbackQueryHandler(service_select, pattern=r'^svc:\d+$'))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r'^(adm:|reqview:|reqstatus:|svadmin:|svadd$|svaddstep:|svtoggle:|svdel:)'))
    app.add_handler(CallbackQueryHandler(step_type_callback, pattern=r'^steptype:'))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, admin_command_router), group=1)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, normal_router), group=2)
    app.run_polling()

if __name__ == '__main__':
    main()
