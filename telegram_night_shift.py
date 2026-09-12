"""Tehran business-hours gate and night-shift partner management."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TZ=ZoneInfo("Asia/Tehran")
OPEN=time(7,0); CLOSE=time(19,0)
KEY_PREFIX="night_worker:"


def is_open():
    t=datetime.now(TZ).time()
    return OPEN <= t < CLOSE


def _phone(v):
    s=str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")).replace(" ","").replace("-","")
    if s.startswith("+98"): s="0"+s[3:]
    if s.startswith("0098"): s="0"+s[4:]
    return s if len(s)==11 and s.startswith("09") and s.isdigit() else None


def worker(B,pid):
    try:return B.db.setting(KEY_PREFIX+str(pid),"0")=="1"
    except Exception:return False


def worker_phone(B,phone):
    p=_phone(phone)
    if not p:return False
    r=B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1",(p,)).fetchone()
    return bool(r and worker(B,r["id"]))


def _closed_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 شروع مجدد",callback_data="night:restart")]])


def _closed_text():
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            "🕖 ساعت کاری: ۷ صبح تا ۷ شب به وقت تهران\n"
            "🌙 ساعت تعطیلی: ۷ شب تا ۷ صبح\n\n"
            "لطفاً در ساعت کاری مراجعه کنید.")


def _allowed(B,uid):
    if B.admin(uid): return True
    st=B.S.get(uid,{})
    pid=st.get("partner_id")
    return bool(pid and worker(B,pid))


def install(app,B):
    if getattr(B,"_night_shift_installed",False): return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS night_workers(partner_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL)")
    B.db.conn.commit()
    # DB setting is the compatibility source; table mirrors it for future admin/reporting.
    original_partner=B.partner
    async def guarded_partner(update,context):
        uid=update.effective_user.id
        if not is_open() and not B.admin(uid):
            st=B.S.get(uid,{})
            pid=st.get("partner_id")
            if not pid or not worker(B,pid):
                return await update.message.reply_text(_closed_text(),reply_markup=_closed_markup())
        return await original_partner(update,context)
    B.partner=guarded_partner

    import telegram_admin_plus as A
    old_menu=A._admin_menu
    def admin_menu():
        m=old_menu(); rows=[list(r) for r in m.inline_keyboard]
        rows.insert(-1,[InlineKeyboardButton("🌙 همکاران شب‌کار",callback_data="night:menu")])
        return InlineKeyboardMarkup(rows)
    A._admin_menu=admin_menu

    async def cb(update,context):
        q=update.callback_query
        if not q:return
        d=(q.data or "").split(":")
        if not d or d[0]!="night":return
        uid=q.from_user.id
        if not B.admin(uid):
            await q.answer("دسترسی ندارید",show_alert=True); return
        await q.answer()
        st=B.S.setdefault(uid,{})
        if len(d)>1 and d[1]=="restart":
            return await q.message.reply_text("لطفاً در ساعت کاری مراجعه کنید.")
        if len(d)>1 and d[1]=="menu":
            rows=B.db.conn.execute("SELECT p.id,p.name,p.phone,p.active,COALESCE(n.enabled,0) enabled FROM partners p LEFT JOIN night_workers n ON n.partner_id=p.id ORDER BY p.id DESC").fetchall()
            buttons=[]
            for r in rows:
                state="🟢 شب‌کار" if r["enabled"] else "⚪ عادی"
                buttons.append([InlineKeyboardButton(f"{state} {r['name'] or r['phone']}",callback_data=f"night:toggle:{r['id']}")])
            buttons.append([InlineKeyboardButton("➕ افزودن همکار شب‌کار",callback_data="night:add")])
            buttons.append([InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")])
            return await q.message.reply_text("🌙 مدیریت همکاران شب‌کار\n\nروی نام همکار بزنید تا وضعیت شب‌کاری تغییر کند.",reply_markup=InlineKeyboardMarkup(buttons))
        if len(d)>1 and d[1]=="add":
            st["night_mode"]="add"; return await q.message.reply_text("📱 شماره موبایل همکار شب‌کار را وارد کنید:")
        if len(d)>2 and d[1]=="toggle":
            pid=int(d[2]); enabled=not worker(B,pid)
            B.db.set_setting(KEY_PREFIX+str(pid),"1" if enabled else "0")
            B.db.conn.execute("INSERT OR REPLACE INTO night_workers(partner_id,enabled,updated_at) VALUES(?,?,?)",(pid,1 if enabled else 0,B.now()))
            B.db.conn.commit()
            return await q.message.reply_text("✅ همکار شب‌کار شد." if enabled else "✅ دسترسی شب‌کاری لغو شد.",reply_markup=admin_menu())

    async def text(update,context):
        if not update.message or not B.admin(update.effective_user.id):return
        st=B.S.setdefault(update.effective_user.id,{})
        if st.get("night_mode")!="add":return
        p=_phone(update.message.text)
        if not p:return await update.message.reply_text("❌ شماره موبایل معتبر نیست.")
        row=B.db.conn.execute("SELECT id,name FROM partners WHERE phone=? AND active=1",(p,)).fetchone()
        if not row:return await update.message.reply_text("❌ همکار فعال با این شماره پیدا نشد.")
        B.db.set_setting(KEY_PREFIX+str(row["id"]),"1")
        B.db.conn.execute("INSERT OR REPLACE INTO night_workers(partner_id,enabled,updated_at) VALUES(?,?,?)",(row["id"],1,B.now()));B.db.conn.commit()
        st["night_mode"]=None
        return await update.message.reply_text(f"✅ {row['name'] or p} به همکاران شب‌کار اضافه شد.",reply_markup=admin_menu())

    async def gate(update,context):
        if is_open():return
        msg=getattr(update,"effective_message",None)
        user=getattr(update,"effective_user",None)
        if not msg or not user or B.admin(user.id) or _allowed(B,user.id):return
        await msg.reply_text(_closed_text(),reply_markup=_closed_markup())
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb,pattern=r"^night:"),group=-2100)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-2099)
    app.add_handler(MessageHandler(filters.ALL,gate),group=-2098)
    B._night_shift_installed=True
