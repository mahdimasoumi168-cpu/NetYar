"""Single business-hours gate for Telegram.

Outside normal hours the bot shows only the warning plus two options:
«شروع مجدد» and «پنل همکاران». The partner option is usable only by partners
that were already configured as night-shift workers.
"""
from datetime import datetime,time
from zoneinfo import ZoneInfo
from telegram import ReplyKeyboardMarkup,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler,MessageHandler,ApplicationHandlerStop,filters

TZ=ZoneInfo("Asia/Tehran");OPEN=time(7,0);CLOSE=time(19,0)
PREFIX="night_worker:";RESTART="🔄 شروع مجدد";PARTNER_PANEL="👥 پنل همکاران"


def is_friday(): return datetime.now(TZ).weekday()==4

def open_now():
    if is_friday(): return False
    t=datetime.now(TZ).time(); return OPEN<=t<CLOSE


def phone(v):
    s=str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")).replace(" ","").replace("-","")
    if s.startswith("+98"): s="0"+s[3:]
    if s.startswith("0098"): s="0"+s[4:]
    return s if len(s)==11 and s.startswith("09") and s.isdigit() else None


def worker(B,pid): return bool(pid and B.db.setting(PREFIX+str(pid),"0")=="1")

def worker_phone(B,v):
    p=phone(v)
    if not p:return False
    r=B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1",(p,)).fetchone()
    return bool(r and worker(B,r["id"]))


def night_partner_allowed(B,uid):
    st=B.S.get(uid,{})
    return bool(worker(B,st.get("partner_id")) or worker_phone(B,st.get("phone")))


def allowed(B,uid,update=None):
    if B.admin(uid): return True
    if night_partner_allowed(B,uid): return True
    if update:
        msg=getattr(update,"effective_message",None); txt=(getattr(msg,"text","") or "").strip() if msg else ""
        if txt==PARTNER_PANEL and night_partner_allowed(B,uid): return True
    return False


def closed():
    if is_friday():
        return "⛔ ربات در حال حاضر تعطیل است.\n\n🕖 خدمات عادی از شنبه ساعت ۷ صبح فعال می‌شود.\n🌙 فقط همکاران شیفت شبِ از قبل تعریف‌شده می‌توانند وارد پنل همکاران شوند."
    return "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n🕖 ساعت کاری: ۷ صبح تا ۷ شب به وقت تهران\n🌙 فقط همکاران شیفت شبِ از قبل تعریف‌شده به پنل همکاران دسترسی دارند.\n\nلطفاً در ساعت کاری برای خدمات عادی مراجعه کنید."


def markup():
    return ReplyKeyboardMarkup([[RESTART,PARTNER_PANEL]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)


def _opening_markup(B,uid=None):
    return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)


async def _broadcast_opening(context,B):
    now=datetime.now(TZ)
    if is_friday() or not (OPEN<=now.time()<time(7,2)): return
    day=now.strftime("%Y-%m-%d")
    if B.db.setting("opening_notice_date","")==day:return
    rows=B.db.conn.execute("SELECT external_id FROM users WHERE platform='telegram' AND external_id IS NOT NULL").fetchall()
    text="🟢 ربات باز شد\n\nساعت کاری عادی شروع شد. برای نمایش منوی خدمات «🔄 شروع مجدد» را بزنید."
    sent=0
    for r in rows:
        try:
            await context.bot.send_message(chat_id=int(r["external_id"]),text=text,reply_markup=_opening_markup(B,r["external_id"]))
            sent+=1
        except Exception: pass
    B.db.set_setting("opening_notice_date",day)
    try:B.db.set_setting("opening_notice_count",str(sent))
    except Exception:pass


def install(app,B):
    if getattr(B,"_night_shift_v2",False):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS night_workers(partner_id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL)");B.db.conn.commit()
    old_partner=B.partner

    async def partner(update,context):
        uid=update.effective_user.id
        if not open_now() and not B.admin(uid) and not night_partner_allowed(B,uid):
            return await update.effective_message.reply_text(closed(),reply_markup=markup())
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
        q=update.callback_query; d=(q.data or "").split(":")
        if not q or not d or d[0]!="night2":return
        await q.answer()
        if len(d)<2:return
        if d[1]=="restart":
            if not open_now() and not B.admin(q.from_user.id) and not night_partner_allowed(B,q.from_user.id):
                return await q.message.reply_text(closed(),reply_markup=markup())
            return await B.start(type("U",(),{"message":q.message,"effective_message":q.message,"effective_user":q.from_user})(),context)
        uid=q.from_user.id
        if not B.admin(uid):return await q.answer("دسترسی ندارید",show_alert=True)
        st=B.S.setdefault(uid,{})
        if d[1]=="menu":
            rows=B.db.conn.execute("SELECT p.id,p.name,p.phone,COALESCE(n.enabled,0) enabled FROM partners p LEFT JOIN night_workers n ON n.partner_id=p.id ORDER BY p.id DESC").fetchall();buttons=[]
            for r in rows:buttons.append([InlineKeyboardButton(("🟢 " if r["enabled"] else "⚪ ")+f"{r['name'] or r['phone']}",callback_data=f"night2:toggle:{r['id']}")])
            buttons += [[InlineKeyboardButton("➕ افزودن همکار شب‌کار",callback_data="night2:add")],[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")]]
            return await q.message.reply_text("🌙 مدیریت همکاران شب‌کار\n\n🟢 = مجاز خارج از ساعت کاری و جمعه\n⚪ = فقط ساعت کاری عادی",reply_markup=InlineKeyboardMarkup(buttons))
        if d[1]=="add":
            st["night_mode"]="add";return await q.message.reply_text("📱 شماره موبایل همکار شب‌کار را وارد کنید:")
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

    async def callback_gate(update,context):
        q=getattr(update,"callback_query",None)
        if not q:return
        uid=q.from_user.id
        if open_now() or B.admin(uid) or night_partner_allowed(B,uid):return
        data=str(q.data or "")
        if data.startswith("night2:"):return
        if data.startswith("ui2:"):
            token=data[4:]
            try:
                row=B.db.conn.execute("SELECT label FROM ui2_callbacks WHERE token=? AND user_id=? LIMIT 1",(token,str(uid))).fetchone()
            except Exception: row=None
            if row and str(row["label"])==PARTNER_PANEL and night_partner_allowed(B,uid):return
        try:await q.answer("⏰ خارج از ساعت کاری است؛ فقط پنل همکاران شیفت شب مجاز است.",show_alert=True)
        except Exception:pass
        try:await q.message.reply_text(closed(),reply_markup=markup())
        finally:raise ApplicationHandlerStop

    async def gate(update,context):
        if open_now() or B.admin(update.effective_user.id) or night_partner_allowed(B,update.effective_user.id):return
        msg=getattr(update,"effective_message",None)
        if not msg:return
        # Outside hours even /start only shows the closed gate; it never opens
        # the normal language/service flow.
        await msg.reply_text(closed(),reply_markup=markup()); raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb,pattern=r"^night2:"),group=-2200)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-2199)
    app.add_handler(MessageHandler(filters.ALL,gate),group=-2198)
    app.add_handler(CallbackQueryHandler(callback_gate),group=-2197)
    try:
        if getattr(app,"job_queue",None): app.job_queue.run_repeating(_broadcast_opening,interval=30,first=5,data=B,name="netyar-opening-broadcast")
    except Exception:
        import logging;logging.getLogger("netyar.night").exception("opening broadcast scheduler unavailable")
    B._night_shift_v2=True
