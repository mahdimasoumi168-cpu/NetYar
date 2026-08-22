import os, logging, asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from .core import db, utcnow

log=logging.getLogger("netyar.telegram")
ACTIVE={}

def menu(uid):
    keys=["services","track","announcements","support","about"]
    rows=[[db.button(k)[0] for k in keys[i:i+2] if db.button(k)[1]] for i in range(0,len(keys),2)]
    if db.is_admin("telegram",uid): rows.append([db.button("admin")[0]])
    return ReplyKeyboardMarkup([r for r in rows if r],resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
      ["📊 داشبورد","📋 درخواست‌ها"],["🏢 خدمات","👥 مشتریان"],
      ["💳 پرداخت و کدها","👨‍💼 مدیران"],["📢 پیام همگانی","📝 تنظیمات"],
      ["📜 لاگ فعالیت","🟢 باز کردن","🔴 بستن"],["⬅️ بازگشت"]],resize_keyboard=True)

async def start(update,ctx):
    u=update.effective_user; db.user(u.id,"telegram",u.username,u.full_name)
    if db.setting("bot_open","1")!="1" and not db.is_admin("telegram",u.id):
        return await update.message.reply_text(db.setting("maintenance"))
    await update.message.reply_text(db.setting("welcome"),reply_markup=menu(u.id))

async def admin(update,ctx):
    if not db.is_admin("telegram",update.effective_user.id): return await update.message.reply_text("⛔ دسترسی ندارید.")
    db.audit("telegram",update.effective_user.id,"admin_open")
    await update.message.reply_text("🔐 پنل مدیریت حرفه‌ای\nاز اینجا همه بخش‌های مدیریتی کنترل می‌شود.",reply_markup=admin_menu())

async def myid(update,ctx):
    await update.message.reply_text(f"🆔 {update.effective_user.id}\nنقش: {db.role('telegram',update.effective_user.id)}")

async def services(update,ctx):
    rows=db.services(True)
    if not rows:return await update.message.reply_text("هنوز خدمتی فعال نیست.")
    await update.message.reply_text("خدمت را انتخاب کنید:",reply_markup=InlineKeyboardMarkup(
      [[InlineKeyboardButton(f"{r['name']} — {r['price']:,} تومان" if r["price"] else r["name"],callback_data=f"svc:{r['id']}")] for r in rows]))

async def svc(update,ctx):
    q=update.callback_query; await q.answer()
    sid=int(q.data.split(":")[1]); s=db.service(sid,True)
    if not s:return await q.edit_message_text("این خدمت دیگر فعال نیست.")
    steps=db.steps(sid)
    rid=db.conn.execute("""INSERT INTO requests(user_id,service_id,platform,status,amount,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?)""",(q.from_user.id,sid,"telegram","collecting",s["price"],utcnow(),utcnow())).lastrowid
    db.conn.commit()
    ACTIVE[q.from_user.id]={"rid":rid,"sid":sid,"idx":0,"code_ok":False}
    await q.edit_message_text(f"🏢 {s['name']}\n{s['description']}\n💰 {s['price']:,} تومان\n\n"+(steps[0]["prompt"] if steps else "این خدمت مرحله‌ای ندارد."))

async def service_input(update,ctx):
    uid=update.effective_user.id; state=ACTIVE.get(uid)
    if not state:return False
    steps=db.steps(state["sid"])
    if state["idx"]>=len(steps):return False
    st=steps[state["idx"]]
    text=update.message.text or ""
    file_id=""
    if update.message.document:
        text=update.message.document.file_name or "file"; file_id=update.message.document.file_id
        if st["input_type"] not in ("file","any"): return await update.message.reply_text("این مرحله متن می‌خواهد.")
    elif update.message.photo:
        text="photo"; file_id=update.message.photo[-1].file_id
        if st["input_type"] not in ("image","file","any"): return await update.message.reply_text("این مرحله متن می‌خواهد.")
    elif st["input_type"] in ("file","image"):
        return await update.message.reply_text("لطفاً فایل یا عکس ارسال کنید.")
    if st["required"] and not text.strip(): return await update.message.reply_text("این مورد اجباری است.")
    db.conn.execute("INSERT INTO request_answers(request_id,step_id,answer,file_id,created_at) VALUES(?,?,?,?,?)",
                    (state["rid"],st["id"],text,file_id,utcnow()))
    db.conn.commit(); state["idx"]+=1
    if state["idx"]<len(steps):
        return await update.message.reply_text(steps[state["idx"]]["prompt"])
    s=db.service(state["sid"]); methods=[x.strip() for x in s["payment_methods"].split(",") if x.strip()]
    kb=[]
    if "code" in methods: kb.append([InlineKeyboardButton("🎟 کد اختصاصی",callback_data=f"pay:{state['rid']}:code")])
    if "card" in methods: kb.append([InlineKeyboardButton("💳 کارت‌به‌کارت",callback_data=f"pay:{state['rid']}:card")])
    if not kb:
        db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',updated_at=? WHERE id=?",(utcnow(),state["rid"])); db.conn.commit()
        ACTIVE.pop(uid,None); return await update.message.reply_text(f"درخواست #{state['rid']} ثبت شد ✅",reply_markup=menu(uid))
    await update.message.reply_text("اطلاعات دریافت شد. روش پرداخت را انتخاب کنید:",reply_markup=InlineKeyboardMarkup(kb))
    return True

async def payment(update,ctx):
    q=update.callback_query; await q.answer()
    _,rid,method=q.data.split(":"); rid=int(rid)
    r=db.conn.execute("SELECT * FROM requests WHERE id=? AND user_id=?",(rid,q.from_user.id)).fetchone()
    if not r:return await q.edit_message_text("درخواست پیدا نشد.")
    if method=="code":
        ACTIVE[q.from_user.id]["await_code"]=rid
        return await q.message.reply_text("کد اختصاصی را ارسال کنید:")
    db.conn.execute("UPDATE requests SET payment_method='card',payment_status='pending',status='awaiting_payment',updated_at=? WHERE id=?",(utcnow(),rid)); db.conn.commit()
    card=db.setting("card_number","ثبت نشده"); owner=db.setting("card_owner","")
    await q.message.reply_text(f"💳 کارت‌به‌کارت\nشماره کارت: {card}\nبه نام: {owner}\n\nبعد از واریز، رسید را همینجا ارسال کنید.")
    ACTIVE[q.from_user.id]["await_receipt"]=rid

async def code_or_receipt(update,ctx):
    uid=update.effective_user.id; st=ACTIVE.get(uid)
    if not st:return False
    if st.get("await_code"):
        code=update.message.text.strip()
        ok,info=db.validate_code(code,uid,st["sid"])
        if not ok:return await update.message.reply_text("❌ "+info)
        db.consume_code(code)
        rid=st["await_code"]; db.conn.execute("UPDATE requests SET payment_method='code',payment_status='paid',status='submitted',updated_at=? WHERE id=?",(utcnow(),rid)); db.conn.commit()
        st.pop("await_code",None); ACTIVE.pop(uid,None)
        return await update.message.reply_text(f"کد تایید شد و درخواست #{rid} ثبت شد ✅",reply_markup=menu(uid))
    if st.get("await_receipt"):
        rid=st["await_receipt"]; fid=""
        if update.message.photo: fid=update.message.photo[-1].file_id
        elif update.message.document: fid=update.message.document.file_id
        else:return await update.message.reply_text("رسید را به صورت عکس یا فایل ارسال کنید.")
        db.conn.execute("UPDATE requests SET payment_method='card',payment_status='pending',status='payment_review',payment_note=?,updated_at=? WHERE id=?",(fid,utcnow(),rid)); db.conn.commit()
        db.audit("telegram",uid,"payment_receipt",rid)
        st.pop("await_receipt",None)
        return await update.message.reply_text("رسید دریافت شد و برای بررسی مدیر ارسال می‌شود. ✅")
    return False

async def track(update,ctx):
    parts=(update.message.text or "").split()
    if len(parts)<2:return await update.message.reply_text("کد درخواست را بعد از /track بفرستید؛ مثال: /track 12")
    try: rid=int(parts[1])
    except: return await update.message.reply_text("کد درخواست نامعتبر است.")
    r=db.conn.execute("SELECT r.*,s.name FROM requests r JOIN services s ON s.id=r.service_id WHERE r.id=? AND r.user_id=?",(rid,update.effective_user.id)).fetchone()
    if not r:return await update.message.reply_text("درخواست پیدا نشد.")
    await update.message.reply_text(f"📋 #{rid}\nخدمت: {r['name']}\nوضعیت: {r['status']}\nپرداخت: {r['payment_status']}")

async def admin_dashboard(update,ctx):
    if not db.can("telegram",update.effective_user.id,"reports"):return
    c=lambda q:db.conn.execute(q).fetchone()[0]
    users=c("SELECT COUNT(*) FROM users")
    services_count=c("SELECT COUNT(*) FROM services WHERE active=1")
    requests_count=c("SELECT COUNT(*) FROM requests")
    pending=c("SELECT COUNT(*) FROM requests WHERE payment_status='pending'")
    open_requests=c("SELECT COUNT(*) FROM requests WHERE status NOT IN ('done','rejected')")
    await update.message.reply_text(f"📊 داشبورد\\nکاربران: {users}\\nخدمات فعال: {services_count}\\nدرخواست‌ها: {requests_count}\\nدر انتظار پرداخت: {pending}\\nدرخواست باز: {open_requests}")

async def admin_requests(update,ctx):
    if not db.can("telegram",update.effective_user.id,"requests"):return
    rows=db.conn.execute("""SELECT r.id,r.status,r.payment_status,r.amount,u.full_name,s.name
      FROM requests r JOIN users u ON u.id=r.user_id JOIN services s ON s.id=r.service_id ORDER BY r.id DESC LIMIT 50""").fetchall()
    text="📋 آخرین درخواست‌ها\n\n"+("\n".join(f"#{r['id']} | {r['name']} | {r['full_name'] or '-'} | {r['status']} | {r['payment_status']}" for r in rows) or "موردی نیست.")
    await update.message.reply_text(text[:4000])

async def admin_services(update,ctx):
    if not db.can("telegram",update.effective_user.id,"services"):return
    rows=db.services(False)
    kb=[[InlineKeyboardButton(f"{'🟢' if r['active'] else '🔴'} {r['name']}",callback_data=f"asvc:{r['id']}")] for r in rows]
    await update.message.reply_text("🏢 مدیریت خدمات\nاز این بخش در نسخه بعدی سرویس‌ساز کامل فعال می‌شود.",reply_markup=InlineKeyboardMarkup(kb) if kb else None)

async def admin_users(update,ctx):
    if not db.can("telegram",update.effective_user.id,"users"):return
    n=db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    await update.message.reply_text(f"👥 تعداد مشتریان: {n}")

async def admin_codes(update,ctx):
    if not db.can("telegram",update.effective_user.id,"services"):return
    await update.message.reply_text("برای ساخت کد: /newcode [uses] [service_id اختیاری]\nمثال: /newcode 5")

async def newcode(update,ctx):
    if not db.can("telegram",update.effective_user.id,"services"):return
    uses=int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else 1
    sid=int(ctx.args[1]) if len(ctx.args)>1 and ctx.args[1].isdigit() else None
    code=db.create_code(uses=uses,service_id=sid)
    db.audit("telegram",update.effective_user.id,"create_code",code,f"uses={uses},service={sid}")
    await update.message.reply_text(f"🎟 کد جدید: {code}\nدفعات مجاز: {uses}\nخدمت: {sid or 'همه'}")

async def broadcast(update,ctx):
    if not db.can("telegram",update.effective_user.id,"broadcast"):return
    text=" ".join(ctx.args).strip()
    if not text:return await update.message.reply_text("متن را بعد از /broadcast بنویس.")
    rows=db.conn.execute("SELECT id FROM users WHERE platform='telegram'").fetchall(); ok=0
    for r in rows:
        try: await ctx.application.bot.send_message(r["id"],text); ok+=1
        except Exception: pass
    db.audit("telegram",update.effective_user.id,"broadcast",details=f"sent={ok}")
    await update.message.reply_text(f"ارسال شد: {ok}")

async def settings(update,ctx):
    if not db.can("telegram",update.effective_user.id,"services"):return
    await update.message.reply_text(f"⚙️ کارت: {db.setting('card_number','-')}\nنام صاحب کارت: {db.setting('card_owner','-')}\nوضعیت: {'باز' if db.setting('bot_open')=='1' else 'بسته'}\nبرای تغییر کارت: /setcard شماره_کارت نام_صاحب")

async def setcard(update,ctx):
    if not db.is_admin("telegram",update.effective_user.id):return
    if len(ctx.args)<2:return await update.message.reply_text("فرمت: /setcard شماره_کارت نام_صاحب")
    db.set_setting("card_number",ctx.args[0]); db.set_setting("card_owner"," ".join(ctx.args[1:])); db.audit("telegram",update.effective_user.id,"set_card")
    await update.message.reply_text("اطلاعات کارت ذخیره شد ✅")

async def toggle(update,ctx):
    if not db.is_admin("telegram",update.effective_user.id):return
    value="0" if update.message.text.startswith("/close") else "1"; db.set_setting("bot_open",value); db.audit("telegram",update.effective_user.id,"toggle_bot",details=value)
    await update.message.reply_text("انجام شد.")

async def text_router(update,ctx):
    if await code_or_receipt(update,ctx): return
    if await service_input(update,ctx): return
    t=update.message.text or ""
    mapping={db.button("services")[0]:services,db.button("track")[0]:lambda u,c:u.message.reply_text("از /track استفاده کنید."),
             db.button("announcements")[0]:lambda u,c:u.message.reply_text(db.setting("announcements")),
             db.button("support")[0]:lambda u,c:u.message.reply_text(db.setting("support")),
             db.button("about")[0]:lambda u,c:u.message.reply_text(db.setting("about"))}
    if t in mapping:return await mapping[t](update,ctx)
    if not db.is_admin("telegram",update.effective_user.id):return
    admin_map={"📊 داشبورد":admin_dashboard,"📋 درخواست‌ها":admin_requests,"🏢 خدمات":admin_services,"👥 مشتریان":admin_users,
               "💳 پرداخت و کدها":admin_codes,"📢 پیام همگانی":lambda u,c:broadcast(u,c),"📝 تنظیمات":settings}
    if t in admin_map:return await admin_map[t](update,ctx)

def build():
    token=os.getenv("BOT_TOKEN")
    if not token: raise RuntimeError("BOT_TOKEN environment variable is missing.")
    app=Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin))
    app.add_handler(CommandHandler("myid",myid))
    app.add_handler(CommandHandler("track",track))
    app.add_handler(CommandHandler("newcode",newcode))
    app.add_handler(CommandHandler("broadcast",broadcast))
    app.add_handler(CommandHandler("setcard",setcard))
    app.add_handler(CommandHandler("open",toggle))
    app.add_handler(CommandHandler("close",toggle))
    app.add_handler(CallbackQueryHandler(svc,pattern=r"^svc:\d+$"))
    app.add_handler(CallbackQueryHandler(payment,pattern=r"^pay:\d+:(code|card)$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, text_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_router))
    return app