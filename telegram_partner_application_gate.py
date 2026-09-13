"""Approval-gated Telegram partner onboarding.

New users may submit a partner application, but receive no partner services
until an admin approves it. Existing approved partners keep normal login.
"""
import logging, re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop
log=logging.getLogger("netyar.partner_gate")
CANCEL="❌ انصراف"

def _phone(v):
    s=str(v or "").strip().replace(" ","").replace("-","").replace("(","").replace(")","")
    s=s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
    if s.startswith("+98"): s="0"+s[3:]
    elif s.startswith("0098"): s="0"+s[4:]
    return s if re.fullmatch(r"09\d{9}",s) else None

def _ensure(B):
    B.db.conn.executescript("""
    CREATE TABLE IF NOT EXISTS partner_applications(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      telegram_user_id TEXT NOT NULL,
      phone TEXT NOT NULL,
      office_name TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      tracking_code TEXT UNIQUE NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      reviewed_at TEXT,
      reviewed_by TEXT,
      reject_reason TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_partner_apps_status ON partner_applications(status);
    """)
    B.db.conn.commit()

def _tracking(B):
    import secrets
    while True:
        code="HAM-"+secrets.token_hex(4).upper()
        if not B.db.conn.execute("SELECT 1 FROM partner_applications WHERE tracking_code=?",(code,)).fetchone(): return code

def _pending(B,uid):
    return B.db.conn.execute("SELECT * FROM partner_applications WHERE telegram_user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",(str(uid),)).fetchone()

def _app_menu(B):
    return B.kb([["🤝 درخواست همکاری"],["🔎 پیگیری درخواست همکاری"],[CANCEL]])

def _admin_apps(B):
    rows=B.db.conn.execute("SELECT id,office_name,phone,tracking_code,created_at FROM partner_applications WHERE status='pending' ORDER BY id DESC LIMIT 30").fetchall()
    buttons=[]
    for r in rows:
        buttons.append([InlineKeyboardButton(f"🤝 {r['office_name']} | {r['phone']}",callback_data=f"pa:view:{r['id']}")])
    return InlineKeyboardMarkup(buttons or [[InlineKeyboardButton("موردی وجود ندارد",callback_data="pa:none")]])

async def _partner_entry(update,context,B):
    msg=update.message
    if not msg:return
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    text=(msg.text or "").strip()
    if text not in {"👥 پنل همکاران","🔵 👥 پنل همکاران","پنل همکاران"} and st.get("partner_gate_mode") is None:return
    if text in {"👥 پنل همکاران","🔵 👥 پنل همکاران","پنل همکاران"}:
        p=B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1",(_phone(st.get("phone")),)).fetchone() if _phone(st.get("phone")) else None
        if p and st.get("partner_id")==p["id"]:
            await msg.reply_text(f"👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 اعتبار: {int(p['balance'] or 0):,} تومان",reply_markup=B.partner_kb());raise ApplicationHandlerStop
        pending=_pending(B,uid)
        if pending:
            await msg.reply_text(f"⏳ درخواست همکاری شما در انتظار بررسی مدیریت است.\n\n🎫 کد پیگیری: {pending['tracking_code']}",reply_markup=_app_menu(B));raise ApplicationHandlerStop
        st.update(partner_gate_mode="phone",partner_registration={})
        await msg.reply_text("👥 ورود به پنل همکاران\n\n📱 شماره موبایل خود را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
    mode=st.get("partner_gate_mode"); reg=st.setdefault("partner_registration",{})
    if mode=="phone":
        p=_phone(text)
        if not p:
            await msg.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
        row=B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1",(p,)).fetchone()
        if row:
            st.update(phone=p,partner_gate_mode=None,partner_registration=None,mode="p_pass")
            await msg.reply_text("🔐 رمز عبور همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
        pending=B.db.conn.execute("SELECT * FROM partner_applications WHERE phone=? AND status='pending' ORDER BY id DESC LIMIT 1",(p,)).fetchone()
        if pending:
            st["partner_gate_mode"]=None
            await msg.reply_text(f"⏳ برای این شماره یک درخواست همکاری در انتظار بررسی است.\n🎫 کد پیگیری: {pending['tracking_code']}",reply_markup=_app_menu(B));raise ApplicationHandlerStop
        reg["phone"]=p;st["partner_gate_mode"]="password"
        await msg.reply_text("🔐 یک رمز عبور جدید برای پنل همکاران انتخاب کنید:\n\nحداقل ۶ کاراکتر.",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
    if mode=="password":
        if len(text)<6:
            await msg.reply_text("❌ رمز عبور باید حداقل ۶ کاراکتر باشد.",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
        reg["password"]=text;st["partner_gate_mode"]="office"
        await msg.reply_text("🏢 نام دفتر یا محل فعالیت را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
    if mode=="office":
        if len(text)<2:
            await msg.reply_text("❌ نام دفتر را کامل وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
        reg["office_name"]=text
        from core import hash_password
        code=_tracking(B)
        B.db.conn.execute("INSERT INTO partner_applications(telegram_user_id,phone,office_name,password_hash,status,tracking_code,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(str(uid),reg["phone"],reg["office_name"],hash_password(reg["password"]),"pending",code,B.now(),B.now()))
        B.db.conn.commit();st["partner_gate_mode"]=None;st["partner_registration"]={}
        await B.notify_admins(context.application,f"🤝 درخواست همکاری جدید\n\n🎫 کد پیگیری: {code}\n👤 نام دفتر: {reg['office_name']}\n📱 شماره: {reg['phone']}\n🆔 تلگرام: {uid}\n\nدرخواست در پنل مدیریت قابل تأیید یا رد است.")
        await msg.reply_text(f"✅ درخواست همکاری شما ثبت شد.\n\n🎫 کد پیگیری: {code}\n⏳ وضعیت: در انتظار بررسی مدیریت\n\nتا زمان تأیید، هیچ‌یک از خدمات پنل همکاران برای شما فعال نیست.",reply_markup=_app_menu(B));raise ApplicationHandlerStop

async def _text(update,context,B):
    if not update.message:return
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    text=(update.message.text or "").strip()
    if text=="🤝 درخواست همکاری":
        p=_pending(B,uid)
        if p:
            await update.message.reply_text(f"⏳ درخواست شما قبلاً ثبت شده است.\n🎫 {p['tracking_code']}",reply_markup=_app_menu(B));raise ApplicationHandlerStop
        st["partner_gate_mode"]="phone";st["partner_registration"]={}
        await update.message.reply_text("📱 شماره موبایل خود را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")));raise ApplicationHandlerStop
    if text=="🔎 پیگیری درخواست همکاری":
        p=B.db.conn.execute("SELECT * FROM partner_applications WHERE telegram_user_id=? ORDER BY id DESC LIMIT 1",(str(uid),)).fetchone()
        if not p:
            await update.message.reply_text("ℹ️ هنوز درخواست همکاری ثبت نکرده‌اید.",reply_markup=_app_menu(B));raise ApplicationHandlerStop
        status={"pending":"⏳ در انتظار بررسی","approved":"✅ تأیید شده","rejected":"❌ رد شده"}.get(p["status"],p["status"])
        await update.message.reply_text(f"🎫 کد پیگیری: {p['tracking_code']}\n🏢 دفتر: {p['office_name']}\n📌 وضعیت: {status}",reply_markup=_app_menu(B));raise ApplicationHandlerStop
    if B.admin(uid) and text=="🤝 درخواست‌های همکاری":
        await update.message.reply_text("🤝 درخواست‌های همکاری در انتظار بررسی:",reply_markup=_admin_apps(B));raise ApplicationHandlerStop

async def _cb(update,context,B):
    q=update.callback_query
    if not q or not str(q.data or "").startswith("pa:"):return
    await q.answer();uid=q.from_user.id;d=str(q.data).split(":")
    if d[1]=="none":raise ApplicationHandlerStop
    if not B.admin(uid):
        await q.message.reply_text("❌ دسترسی ندارید.");raise ApplicationHandlerStop
    aid=int(d[2]);r=B.db.conn.execute("SELECT * FROM partner_applications WHERE id=?",(aid,)).fetchone()
    if not r:
        await q.message.reply_text("❌ درخواست پیدا نشد.");raise ApplicationHandlerStop
    if d[1]=="view":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید همکاری",callback_data=f"pa:approve:{aid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"pa:reject:{aid}")]])
        await q.message.reply_text(f"🤝 درخواست همکاری\n\n🎫 {r['tracking_code']}\n🏢 نام دفتر: {r['office_name']}\n📱 شماره: {r['phone']}\n🆔 تلگرام: {r['telegram_user_id']}\n📅 ثبت: {r['created_at']}",reply_markup=kb);raise ApplicationHandlerStop
    if d[1] in {"approve","reject"}:
        if r["status"]!="pending":
            await q.message.reply_text("ℹ️ این درخواست قبلاً بررسی شده است.");raise ApplicationHandlerStop
        if d[1]=="reject":
            B.db.conn.execute("UPDATE partner_applications SET status='rejected',reviewed_at=?,reviewed_by=? WHERE id=?",(B.now(),str(uid),aid));B.db.conn.commit()
            try: await context.bot.send_message(int(r["telegram_user_id"]),f"❌ درخواست همکاری شما رد شد.\n🎫 کد پیگیری: {r['tracking_code']}")
            except Exception:pass
            await q.message.reply_text("❌ درخواست رد شد.");raise ApplicationHandlerStop
        exists=B.db.conn.execute("SELECT id FROM partners WHERE phone=?",(r["phone"],)).fetchone()
        if exists:
            pid=exists["id"]
            B.db.conn.execute("UPDATE partners SET name=?,password_hash=?,active=1,updated_at=? WHERE id=?",(r["office_name"],r["password_hash"],B.now(),pid))
        else:
            cur=B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(r["phone"],r["password_hash"],r["office_name"],1,0,B.now(),B.now()));pid=cur.lastrowid
        B.db.conn.execute("UPDATE partner_applications SET status='approved',reviewed_at=?,reviewed_by=? WHERE id=?",(B.now(),str(uid),aid));B.db.conn.commit()
        try:
            B.db.conn.execute("INSERT OR REPLACE INTO partner_telegram_links(partner_id,telegram_user_id,created_at,updated_at) VALUES(?,?,?,?)",(pid,str(r["telegram_user_id"]),B.now(),B.now()));B.db.conn.commit()
        except Exception:pass
        try: await context.bot.send_message(int(r["telegram_user_id"]),f"✅ درخواست همکاری شما تأیید شد.\n🎫 کد پیگیری: {r['tracking_code']}\n\nاکنون می‌توانید وارد پنل همکاران شوید.")
        except Exception:pass
        await q.message.reply_text(f"✅ درخواست {r['tracking_code']} تأیید شد و پنل همکار فعال شد.");raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_partner_application_gate",False):return
    _ensure(B)
    original_partner_kb=B.partner_kb
    B.partner_kb=original_partner_kb
    app.add_handler(CallbackQueryHandler(lambda u,c:_cb(u,c,B),pattern=r"^pa:"),group=-45)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_text(u,c,B)),group=-44)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_partner_entry(u,c,B)),group=-43)
    old_amenu=getattr(B,"amenu",None)
    if old_amenu:
        def amenu():
            m=old_amenu(); return B.kb(m.keyboard+[["🤝 درخواست‌های همکاری"]])
        B.amenu=amenu
    B._partner_application_gate=True
    log.info("partner application gate installed")
