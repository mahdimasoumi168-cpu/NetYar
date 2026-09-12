"""Tehran business-hours gate with Friday closure and admin/night-partner overrides."""
from datetime import datetime,time
from zoneinfo import ZoneInfo
from telegram import ReplyKeyboardMarkup,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler,MessageHandler,ApplicationHandlerStop,filters
TZ=ZoneInfo("Asia/Tehran");OPEN=time(7,0);CLOSE=time(19,0);PREFIX="night_worker:";RESTART="🔄 شروع مجدد"

def is_friday(): return datetime.now(TZ).weekday()==4
def open_now():
    if is_friday(): return False
    t=datetime.now(TZ).time(); return OPEN<=t<CLOSE

def phone(v):
    s=str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")).replace(" ","").replace("-","")
    if s.startswith("+98"):s="0"+s[3:]
    if s.startswith("0098"):s="0"+s[4:]
    return s if len(s)==11 and s.startswith("09") and s.isdigit() else None

def worker(B,pid): return bool(pid and B.db.setting(PREFIX+str(pid),"0")=="1")

def worker_phone(B,v):
    p=phone(v)
    if not p:return False
    r=B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1",(p,)).fetchone();return bool(r and worker(B,r["id"]))

def allowed(B,uid,update=None):
    # Management always has access, including Friday and outside working hours.
    if B.admin(uid): return True
    st=B.S.get(uid,{})
    if worker(B,st.get("partner_id")):return True
    if worker_phone(B,st.get("phone")):return True
    if st.get("mode") in {"p_phone","p_pass"}:return True
    if update:
        msg=getattr(update,"effective_message",None);txt=getattr(msg,"text","") if msg else ""
        if txt and txt.strip() in {RESTART,"شروع مجدد","/start","start"}: return True
        if txt and "پنل همکاران" in txt:return True
        if worker_phone(B,txt):return True
    return False

def closed():
    if is_friday():return "⛔ امروز جمعه است و ربات خدمات عادی تعطیل می‌باشد.\n\n👤 مدیریت و همکاران شیفت شبِ تعریف‌شده همچنان دسترسی دارند.\n📅 فعالیت عادی از شنبه ادامه خواهد داشت."
    return "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n🕖 ساعت کاری عادی: ۷ صبح تا ۷ شب به وقت تهران\n🌙 دسترسی شبانه: فقط مدیریت و همکاران شیفت شبِ تعریف‌شده\n\nلطفاً در ساعت کاری مراجعه کنید."

def markup():return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)

def install(app,B):
    if getattr(B,"_night_shift_v2",False):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS night_workers(partner_id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL)");B.db.conn.commit()
    old_partner=B.partner
    async def partner(update,context):
        if not open_now() and not allowed(B,update.effective_user.id,update):return await update.effective_message.reply_text(closed(),reply_markup=markup())
        return await old_partner(update,context)
    B.partner=partner
    import telegram_admin_plus as A
    old_menu=A._admin_menu
    def menu():
        m=old_menu();rows=[list(r) for r in m.inline_keyboard]
        if not any(any(getattr(b,"callback_data","")=="night2:menu" for b in r) for r in rows):
            rows.insert(max(0,len(rows)-1),[InlineKeyboardButton("🌙 همکاران شب‌کار",callback_data="night2:menu")])
        return InlineKeyboardMarkup(rows)
    A._admin_menu=menu
    async def cb(update,context):
        q=update.callback_query;d=(q.data or "").split(":")
        if not q or not d or d[0]!="night2":return
        await q.answer()
        if len(d)<2:return
        if d[1]=="restart":return await q.message.reply_text(closed(),reply_markup=markup())
        uid=q.from_user.id
        if not B.admin(uid):return await q.answer("دسترسی ندارید",show_alert=True)
        st=B.S.setdefault(uid,{})
        if d[1]=="menu":
            rows=B.db.conn.execute("SELECT p.id,p.name,p.phone,COALESCE(n.enabled,0) enabled FROM partners p LEFT JOIN night_workers n ON n.partner_id=p.id ORDER BY p.id DESC").fetchall();buttons=[]
            for r in rows:buttons.append([InlineKeyboardButton(("🟢 " if r["enabled"] else "⚪ ")+f"{r['name'] or r['phone']}",callback_data=f"night2:toggle:{r['id']}")])
            buttons += [[InlineKeyboardButton("➕ افزودن همکار شب‌کار",callback_data="night2:add")],[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")]]
            return await q.message.reply_text("🌙 مدیریت همکاران شب‌کار\n\n🟢 = مجاز خارج از ساعت کاری و جمعه\n⚪ = فقط ساعت کاری عادی",reply_markup=InlineKeyboardMarkup(buttons))
        if d[1]=="add":st["night_mode"]="add";return await q.message.reply_text("📱 شماره موبایل همکار شب‌کار را وارد کنید:")
        if d[1]=="toggle":
            pid=int(d[2]);en=not worker(B,pid);B.db.set_setting(PREFIX+str(pid),"1" if en else "0");B.db.conn.execute("INSERT OR REPLACE INTO night_workers VALUES(?,?,?)",(pid,1 if en else 0,B.now()));B.db.conn.commit();return await q.message.reply_text("✅ دسترسی شب‌کاری فعال شد." if en else "✅ دسترسی شب‌کاری لغو شد.",reply_markup=menu())
    async def text(update,context):
        if not update.message or not B.admin(update.effective_user.id):return
        st=B.S.setdefault(update.effective_user.id,{})
        if st.get("night_mode")!="add":return
        p=phone(update.message.text);row=B.db.conn.execute("SELECT id,name FROM partners WHERE phone=? AND active=1",(p,)).fetchone() if p else None
        if not row:return await update.message.reply_text("❌ همکار فعال با این شماره پیدا نشد.")
        B.db.set_setting(PREFIX+str(row["id"]),"1");B.db.conn.execute("INSERT OR REPLACE INTO night_workers VALUES(?,?,?)",(row["id"],1,B.now()));B.db.conn.commit();st["night_mode"]=None
        return await update.message.reply_text(f"✅ {row['name'] or p} همکار شب‌کار شد.",reply_markup=menu())
    async def gate(update,context):
        if open_now() or allowed(B,update.effective_user.id,update):return
        msg=getattr(update,"effective_message",None)
        if not msg:return
        # Start/restart is always allowed so the user can see the closed-state UI.
        txt=(getattr(msg,"text","") or "").strip()
        if txt in {"/start","/restart","start","شروع مجدد","🔄 شروع مجدد"}:return
        await msg.reply_text(closed(),reply_markup=markup());raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^night2:"),group=-2200)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-2199)
    app.add_handler(MessageHandler(filters.ALL,gate),group=-2198)
    B._night_shift_v2=True
