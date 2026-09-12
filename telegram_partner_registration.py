"""Telegram partner onboarding and cooperation approval workflow."""
import logging, secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters
log = logging.getLogger("netyar.telegram.partner_registration")

def _phone(B, value):
    fn = getattr(B, "normalize_phone", None)
    return fn(value) if fn else str(value or "").strip()

def _limited(B): return B.kb([["🤝 درخواست همکاری"]])
def _pending(B): return B.kb([["🎫 پیگیری درخواست همکاری"], ["🤝 درخواست همکاری"]])
def _code(): return "NYC-" + secrets.token_hex(4).upper()

def _proxy(q):
    return type("U", (), {"effective_user": q.from_user, "effective_message": q.message, "effective_chat": q.message.chat, "callback_query": q})()

async def _show_new(update, B):
    await update.effective_message.reply_text("👥 پنل همکاران جدید\n\nفعلاً فقط گزینه «🤝 درخواست همکاری» برای شما فعال است.", reply_markup=_limited(B))

async def _show_status(update, B, row):
    s = row["status"]
    if s == "approved":
        return await update.effective_message.reply_text(f"✅ درخواست همکاری تأیید شد.\n\n🎫 کد پیگیری: {row['tracking_code']}\n\nاکنون پنل کامل همکاران برای شما فعال است.", reply_markup=B.partner_kb(B.S.get(update.effective_user.id, {}).get("lang", "fa")))
    if s == "rejected":
        text = f"❌ درخواست همکاری رد شد.\n\n🎫 کد پیگیری: {row['tracking_code']}\n\nمی‌توانید دوباره درخواست همکاری بدهید."
    else:
        text = f"⏳ درخواست همکاری در حال بررسی است.\n\n🎫 کد پیگیری: {row['tracking_code']}"
    await update.effective_message.reply_text(text, reply_markup=_pending(B))

async def partner_entry(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("partner_id") and st.get("partner_active", False): return await B._partner_registration_old(update, context)
    if st.get("partner_id"):
        p = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (st["partner_id"],)).fetchone()
        if p:
            req = B.db.conn.execute("SELECT * FROM partner_requests WHERE partner_id=? ORDER BY id DESC LIMIT 1", (p["id"],)).fetchone()
            if req:
                if req["status"] == "approved":
                    B.db.conn.execute("UPDATE partners SET active=1,updated_at=? WHERE id=?", (B.now(), p["id"])); B.db.conn.commit(); st.update(partner_active=True, mode=None); return await B._partner_registration_old(update, context)
                return await _show_status(update, B, req)
            return await _show_new(update, B)
    st["mode"] = "partner_entry_phone"
    await update.effective_message.reply_text("📱 شماره موبایل همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))

async def _request(update, context, B):
    uid = update.effective_user.id; st = B.S.setdefault(uid, {}); pid = st.get("partner_id")
    p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=0", (pid,)).fetchone()
    if not p: return await update.effective_message.reply_text("⛔ حساب همکار جدید پیدا نشد.", reply_markup=B.main(uid))
    old = B.db.conn.execute("SELECT * FROM partner_requests WHERE partner_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
    if old: return await _show_status(update, B, old)
    code = _code()
    cur = B.db.conn.execute("INSERT INTO partner_requests(telegram_user_id,platform,partner_id,phone,name,status,tracking_code,created_at) VALUES(?,?,?,?,?,?,?,?)", (str(uid),"telegram",pid,p["phone"],p["name"],"pending",code,B.now()))
    req_id = cur.lastrowid; B.db.conn.commit(); st.update(partner_request_id=req_id,partner_pending=True,mode=None)
    mk = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید درخواست همکاری", callback_data=f"partnerreq:approve:{req_id}"), InlineKeyboardButton("❌ رد درخواست همکاری", callback_data=f"partnerreq:reject:{req_id}")]])
    msg = f"🤝 درخواست همکاری جدید\n\n👤 نام/مجموعه: {p['name']}\n📱 موبایل: {p['phone']}\n🎫 کد پیگیری: {code}\n🆔 شناسه درخواست: {req_id}"
    for aid in B.ADM:
        try: await context.bot.send_message(chat_id=int(aid), text=msg, reply_markup=mk)
        except Exception: log.exception("partner cooperation admin notification failed")
    await update.effective_message.reply_text(f"✅ درخواست همکاری ثبت شد.\n\n🎫 کد پیگیری: {code}\n\nدرخواست برای مدیریت ارسال شد.", reply_markup=_pending(B))

async def _track(update, B):
    B.S.setdefault(update.effective_user.id,{})["mode"]="partner_req_track"
    await update.effective_message.reply_text("🎫 کد پیگیری درخواست همکاری را وارد کنید:", reply_markup=B.cancel_kb(B.S[update.effective_user.id].get("lang","fa")))

async def text(update, context, B):
    uid = update.effective_user.id; st = B.S.setdefault(uid, {}); mode = st.get("mode"); t=(update.effective_message.text or "").strip()
    if mode == "partner_entry_phone":
        phone = _phone(B,t)
        if not phone: return await update.effective_message.reply_text("❌ شماره موبایل معتبر نیست.", reply_markup=B.cancel_kb(st.get("lang","fa")))
        active = B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1",(phone,)).fetchone()
        if active: st.update(phone=phone,mode="partner_entry_pass"); return await update.effective_message.reply_text("🔐 رمز عبور را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang","fa")))
        inactive = B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=0",(phone,)).fetchone()
        if inactive: st.update(phone=phone,partner_id=inactive["id"],partner_active=False,mode=None); return await _show_new(update,B)
        st.update(phone=phone,mode="partner_reg_pass"); return await update.effective_message.reply_text("🔐 رمز جدید خود را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang","fa")))
    if mode == "partner_entry_pass":
        p=B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1",(st.get("phone"),)).fetchone()
        if not p or not B.check_password(t,p["password_hash"]): return await update.effective_message.reply_text("❌ اطلاعات ورود نادرست است.", reply_markup=B.cancel_kb(st.get("lang","fa")))
        st.update(partner_id=p["id"],partner_active=True,mode=None); return await B._partner_registration_old(update,context)
    if mode == "partner_reg_pass":
        if len(t)<4: return await update.effective_message.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.", reply_markup=B.cancel_kb(st.get("lang","fa")))
        st.update(partner_password=t,mode="partner_reg_name"); return await update.effective_message.reply_text("👤 نام همکار یا نام مجموعه را وارد کنید.\n\nمثال: کافی نت مهیار اصفهان", reply_markup=B.cancel_kb(st.get("lang","fa")))
    if mode == "partner_reg_name":
        name=t[:120]
        if len(name)<2: return await update.effective_message.reply_text("❌ نام همکار/مجموعه را وارد کنید.", reply_markup=B.cancel_kb(st.get("lang","fa")))
        phone=st.get("phone")
        if B.db.conn.execute("SELECT 1 FROM partners WHERE phone=?",(phone,)).fetchone(): return await update.effective_message.reply_text("❌ این شماره قبلاً ثبت شده است.", reply_markup=B.main(uid))
        from core import hash_password
        cur=B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(phone,hash_password(st.get("partner_password","")),name,0,0,B.now(),B.now()))
        pid=cur.lastrowid; B.db.conn.commit(); st.update(partner_id=pid,partner_active=False,partner_pending=False,mode=None); return await _show_new(update,B)
    if mode == "partner_req_track":
        row=B.db.conn.execute("SELECT * FROM partner_requests WHERE telegram_user_id=? AND tracking_code=? ORDER BY id DESC LIMIT 1",(str(uid),t.upper())).fetchone()
        if not row: return await update.effective_message.reply_text("❌ کد پیگیری پیدا نشد.", reply_markup=_pending(B))
        return await _show_status(update,B,row)
    return None

async def ik(update, context, B):
    q=update.callback_query
    if not q or not str(q.data or "").startswith("ik:"): return
    import telegram_no_reply_keyboard as N
    label=N._ACTIONS.get(str(q.data),"")
    if label not in {"🤝 درخواست همکاری","🎫 پیگیری درخواست همکاری"}: return
    await q.answer(); proxy=_proxy(q)
    if label=="🤝 درخواست همکاری": await _request(proxy,context,B)
    else: await _track(proxy,B)
    raise ApplicationHandlerStop

async def decision(update, context, B):
    q=update.callback_query
    if not q or not str(q.data or "").startswith("partnerreq:"): return
    await q.answer(); uid=q.from_user.id
    if not B.admin(uid): await q.message.reply_text("⛔ این بخش فقط برای مدیریت فعال است."); raise ApplicationHandlerStop
    parts=str(q.data).split(":")
    try: rid=int(parts[2])
    except Exception: await q.message.reply_text("❌ درخواست نامعتبر است."); raise ApplicationHandlerStop
    row=B.db.conn.execute("SELECT * FROM partner_requests WHERE id=?",(rid,)).fetchone()
    if not row: await q.message.reply_text("❌ درخواست همکاری پیدا نشد."); raise ApplicationHandlerStop
    if row["status"]!="pending": await q.message.reply_text(f"ℹ️ این درخواست قبلاً بررسی شده است: {row['status']}"); raise ApplicationHandlerStop
    if parts[1]=="approve":
        B.db.conn.execute("UPDATE partners SET active=1,updated_at=? WHERE id=?",(B.now(),row["partner_id"])); B.db.conn.execute("UPDATE partner_requests SET status='approved',reviewed_at=?,reviewer_id=? WHERE id=?",(B.now(),str(uid),rid)); result=f"✅ درخواست همکاری تأیید شد.\n\n🎫 کد پیگیری: {row['tracking_code']}\n\nحساب همکار فعال شد."
    elif parts[1]=="reject":
        B.db.conn.execute("UPDATE partner_requests SET status='rejected',reviewed_at=?,reviewer_id=? WHERE id=?",(B.now(),str(uid),rid)); result=f"❌ درخواست همکاری رد شد.\n\n🎫 کد پیگیری: {row['tracking_code']}"
    else: await q.message.reply_text("❌ عملیات نامعتبر است."); raise ApplicationHandlerStop
    B.db.conn.commit()
    try: await context.bot.send_message(chat_id=int(row["telegram_user_id"]),text=result+"\n\nبرای پیگیری، گزینه «🎫 پیگیری درخواست همکاری» را بزنید.")
    except Exception: log.exception("partner decision notification failed")
    await q.message.edit_reply_markup(reply_markup=None); await q.message.reply_text(result); raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_partner_registration_v2",False): return
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_user_id TEXT NOT NULL,platform TEXT DEFAULT 'telegram',partner_id INTEGER,phone TEXT NOT NULL,name TEXT NOT NULL,status TEXT DEFAULT 'pending',tracking_code TEXT UNIQUE,created_at TEXT,reviewed_at TEXT,reviewer_id TEXT DEFAULT '',note TEXT DEFAULT '')"""); B.db.conn.commit()
    B.check_password=__import__("core").check_password; B._partner_registration_old=B.partner
    async def partner_wrapper(update,context): return await partner_entry(update,context,B)
    B.partner=partner_wrapper
    app.add_handler(CallbackQueryHandler(lambda u,c: ik(u,c,B),pattern=r"^ik:"),group=-5000)
    app.add_handler(CallbackQueryHandler(lambda u,c: decision(u,c,B),pattern=r"^partnerreq:"),group=-5001)
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,lambda u,c:text(u,c,B),group=-3600))
    B._partner_registration_v2=True
    log.info("Partner onboarding/cooperation workflow installed")
