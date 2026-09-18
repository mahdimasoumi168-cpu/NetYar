"""Canonical Telegram partner authentication and membership onboarding.

Single owner for the partner phone step:
- normalizes Iranian phone numbers and legacy DB formats
- authenticates active partners
- sends unknown/inactive numbers into membership request flow
- never lets legacy p_phone handlers produce the old "active partner" error
"""
import logging, re, secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.partner_registration_v4")
MARK = "_partner_registration_v4"

def _phone(B, value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
    s = re.sub(r"\D", "", s)
    if s.startswith("0098"): s = "0" + s[4:]
    elif s.startswith("98"): s = "0" + s[2:]
    return s if re.fullmatch(r"09\d{9}", s) else ""

def _variants(value):
    p = _phone(None, value)
    if not p: return set()
    return {p, p[1:], "98"+p[1:], "+98"+p[1:], "0098"+p[1:]}

def _lookup(B, phone, active_only=False):
    p = _phone(B, phone)
    if not p: return None
    try:
        sql = "SELECT * FROM partners"
        if active_only: sql += " WHERE active=1"
        sql += " ORDER BY id DESC"
        for row in B.db.conn.execute(sql).fetchall():
            stored = row["phone"] if "phone" in row.keys() else ""
            if _phone(B, stored) == p or _variants(stored) & _variants(p):
                if not active_only or int(row["active"] or 0) == 1:
                    return row
    except Exception:
        log.exception("canonical partner lookup failed")
    return None

def _cancel_kb(B, lang="fa"):
    try: return B.cancel_kb(lang)
    except Exception:
        from telegram import ReplyKeyboardMarkup
        return ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True)

def _new_member_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🤝 درخواست عضویت", callback_data="partnerreg:request"),
                                  InlineKeyboardButton("❌ انصراف", callback_data="partnerreg:cancel")]])

def _pending_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎫 پیگیری درخواست", callback_data="partnerreg:track")],
                                 [InlineKeyboardButton("❌ انصراف", callback_data="partnerreg:cancel")]])

def _code(): return "NYC-" + secrets.token_hex(4).upper()

def _night_allowed(B, uid, row=None):
    try:
        from telegram_offhours_partner_gate_v2 import _clock_is_open, night_shift_enabled, is_night_worker
        if _clock_is_open(B) or B.admin(uid): return True
        if not night_shift_enabled(B): return False
        if row:
            return str(B.db.setting("night_worker:"+str(row["id"]), "0")) == "1"
        return is_night_worker(B, uid)
    except Exception:
        return True

async def _status(update, B, row):
    status = str(row["status"] or "")
    if status == "approved":
        try:
            B.db.conn.execute("UPDATE partners SET active=1,updated_at=? WHERE id=?", (B.now(), row["partner_id"]))
            B.db.conn.commit()
        except Exception: log.exception("activate approved partner failed")
        st=B.S.setdefault(update.effective_user.id,{})
        st.update(partner_id=row["partner_id"], partner_active=True, mode=None, step=None, partner_logged_out=False)
        return await update.effective_message.reply_text("✅ درخواست عضویت شما تأیید شده است.\n\nاکنون می‌توانید با رمز تعیین‌شده وارد پنل همکاران شوید.",
                                                         reply_markup=B.partner_kb(st.get("lang","fa")))
    if status == "rejected":
        return await update.effective_message.reply_text(f"❌ درخواست عضویت شما رد شده است.\n\n🎫 کد پیگیری: {row['tracking_code']}\n\nمی‌توانید دوباره درخواست عضویت ثبت کنید.",
                                                         reply_markup=_new_member_kb())
    return await update.effective_message.reply_text(f"⏳ درخواست عضویت شما در حال بررسی است.\n\n🎫 کد پیگیری: {row['tracking_code']}",
                                                     reply_markup=_pending_kb())

async def partner_entry(update, context, B):
    uid=update.effective_user.id; st=B.S.setdefault(uid,{})
    if st.get("partner_id") and st.get("partner_active") and not st.get("partner_logged_out"):
        row = _lookup(B, st.get("partner_phone") or st.get("phone"), active_only=True)
        if row:
            st.update(partner_id=row["id"], partner_active=True, mode=None, step=None, partner_logged_out=False)
            return await update.effective_message.reply_text(
                f"👥 پنل همکاران\n👤 {row['name'] or '-'}\n📱 {row['phone']}\n💰 اعتبار قابل استفاده: {int(row['balance'] or 0):,} تومان",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )
    for k in ("partner_id","partner_active","partner_pending","partner_request_id","phone","partner_phone","partner_password","partner_reg_name"):
        st.pop(k,None)
    st["mode"]="partner_entry_phone"; st["step"]="partner_entry_phone"
    await update.effective_message.reply_text("👥 ورود به پنل همکاران\n\n📱 شماره موبایل همکار را وارد کنید:",
                                              reply_markup=_cancel_kb(B, st.get("lang","fa")))

async def _request_begin(update, context, B):
    uid=update.effective_user.id; st=B.S.setdefault(uid,{})
    phone=st.get("phone")
    if not phone:
        return await update.effective_message.reply_text("❌ ابتدا شماره موبایل را وارد کنید.")
    row=_lookup(B,phone)
    if row and int(row["active"] or 0)==1:
        st["mode"]="partner_entry_pass"; st["step"]="partner_entry_pass"
        return await update.effective_message.reply_text("🔐 این شماره عضو است. رمز ورود را وارد کنید:", reply_markup=_cancel_kb(B,st.get("lang","fa")))
    if row:
        req=B.db.conn.execute("SELECT * FROM partner_requests WHERE partner_id=? AND status='pending' ORDER BY id DESC LIMIT 1",(row["id"],)).fetchone()
        st.update(partner_id=row["id"],partner_active=False)
        if req:
            st["mode"]=None
            return await _status(update,B,req)
    st["mode"]="partner_reg_pass"; st["step"]="partner_reg_pass"
    await update.effective_message.reply_text("🔐 ابتدا یک رمز ورود برای پنل خود تعیین کنید (حداقل ۴ کاراکتر):", reply_markup=_cancel_kb(B,st.get("lang","fa")))

async def _create_request(update,context,B):
    uid=update.effective_user.id; st=B.S.setdefault(uid,{})
    phone=st.get("phone"); name=(st.get("partner_reg_name") or "").strip()[:120]; password=st.get("partner_password") or ""
    if not phone or len(password)<4 or len(name)<2:
        return await update.effective_message.reply_text("❌ اطلاعات عضویت ناقص است. دوباره درخواست عضویت را شروع کنید.",reply_markup=_new_member_kb())
    from core import hash_password
    now=B.now(); row=_lookup(B,phone)
    if row:
        pid=row["id"]
        if int(row["active"] or 0)==1:
            st["mode"]="partner_entry_pass"; st["step"]="partner_entry_pass"
            return await update.effective_message.reply_text("🔐 این شماره عضو است. رمز ورود را وارد کنید:",reply_markup=_cancel_kb(B,st.get("lang","fa")))
        B.db.conn.execute("UPDATE partners SET password_hash=?,name=?,updated_at=?,phone=? WHERE id=?",(hash_password(password),name,now,phone,pid))
    else:
        cur=B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(phone,hash_password(password),name,0,0,now,now))
        pid=cur.lastrowid
    old=B.db.conn.execute("SELECT * FROM partner_requests WHERE partner_id=? AND status='pending' ORDER BY id DESC LIMIT 1",(pid,)).fetchone()
    if old:
        st.update(partner_id=pid,partner_pending=True,mode=None,step=None)
        return await _status(update,B,old)
    code=_code()
    cur=B.db.conn.execute("INSERT INTO partner_requests(telegram_user_id,platform,partner_id,phone,name,status,tracking_code,created_at) VALUES(?,?,?,?,?,?,?,?)",(str(uid),"telegram",pid,phone,name,"pending",code,now))
    rid=cur.lastrowid; B.db.conn.commit()
    st.update(partner_id=pid,partner_active=False,partner_pending=True,partner_request_id=rid,mode=None,step=None)
    markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید عضویت",callback_data=f"partnerreq:approve:{rid}"),
                                  InlineKeyboardButton("❌ رد عضویت",callback_data=f"partnerreq:reject:{rid}")]])
    msg=f"🤝 درخواست عضویت همکار جدید\n\n👤 نام: {name}\n📱 شماره موبایل: {phone}\n🆔 شناسه درخواست: {rid}\n🎫 کد پیگیری: {code}\n\n⏳ متقاضی درخواست عضویت داده است."
    for aid in (getattr(B,"ADM",[]) or []):
        try: await context.bot.send_message(chat_id=int(aid),text=msg,reply_markup=markup)
        except Exception: log.exception("membership admin notification failed")
    await update.effective_message.reply_text("✅ درخواست عضویت شما با موفقیت ثبت شد.\n\n🎫 کد پیگیری: "+code+"\n\nدرخواست برای مدیریت ارسال شد.",
                                               reply_markup=_pending_kb())

async def text(update,context,B):
    uid=update.effective_user.id; st=B.S.setdefault(uid,{})
    mode=str(st.get("mode") or ""); t=(update.effective_message.text or "").strip()
    if t in {"❌ انصراف","انصراف","لغو"} and (mode.startswith("partner_") or mode in {"p_phone","p_pass","partner_phone","partner_pass"}):
        for k in ("mode","step","partner_password","partner_reg_name","partner_pending","partner_request_id","phone","partner_phone"):
            st.pop(k,None)
        await update.effective_message.reply_text("❌ عملیات عضویت/ورود لغو شد.",reply_markup=B.main(uid))
        raise ApplicationHandlerStop

    if mode in {"partner_entry_phone","p_phone","partner_phone"} or st.get("step") in {"partner_entry_phone","partner_phone"}:
        phone=_phone(B,t)
        if not phone:
            st["mode"]="partner_entry_phone"; st["step"]="partner_entry_phone"
            await update.effective_message.reply_text("❌ شماره موبایل معتبر نیست.\n\n📱 شماره را دوباره وارد کنید:",reply_markup=_cancel_kb(B,st.get("lang","fa")))
            raise ApplicationHandlerStop
        row=_lookup(B,phone,active_only=True)
        if row:
            if not _night_allowed(B,uid,row):
                await update.effective_message.reply_text("🌙 دسترسی شیفت شب برای این همکار فعال نیست.",reply_markup=B.main(uid))
                raise ApplicationHandlerStop
            st.update(phone=phone,partner_phone=phone,partner_id=row["id"],partner_active=True,partner_logged_out=False,mode="partner_entry_pass",step="partner_entry_pass")
            await update.effective_message.reply_text("🔐 رمز عبور پنل همکاران را وارد کنید:",reply_markup=_cancel_kb(B,st.get("lang","fa")))
            raise ApplicationHandlerStop
        # Unknown/inactive number: membership request, never the old 'active partner' error.
        st.update(phone=phone,partner_phone=phone,partner_active=False,mode="partner_new_wait",step="partner_new_wait")
        await update.effective_message.reply_text("👤 این شماره هنوز همکار فعال نیست.\n\nبرای ثبت درخواست عضویت، دکمه زیر را بزنید:",reply_markup=_new_member_kb())
        raise ApplicationHandlerStop

    if mode=="partner_new_wait":
        await update.effective_message.reply_text("ℹ️ برای ادامه، ابتدا دکمه «🤝 درخواست عضویت» را بزنید.",reply_markup=_new_member_kb())
        raise ApplicationHandlerStop

    if mode=="partner_reg_pass":
        if len(t)<4:
            await update.effective_message.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.",reply_markup=_cancel_kb(B,st.get("lang","fa"))); raise ApplicationHandlerStop
        st.update(partner_password=t,mode="partner_reg_name",step="partner_reg_name")
        await update.effective_message.reply_text("👤 نام و نام خانوادگی یا نام مجموعه را وارد کنید:",reply_markup=_cancel_kb(B,st.get("lang","fa"))); raise ApplicationHandlerStop

    if mode=="partner_reg_name":
        if len(t)<2:
            await update.effective_message.reply_text("❌ نام معتبر وارد کنید.",reply_markup=_cancel_kb(B,st.get("lang","fa"))); raise ApplicationHandlerStop
        st["partner_reg_name"]=t[:120]
        await _create_request(update,context,B); raise ApplicationHandlerStop

    if mode=="partner_entry_pass":
        row=_lookup(B,st.get("phone"),active_only=True)
        if not row:
            st["mode"]="partner_entry_phone"; st["step"]="partner_entry_phone"
            await update.effective_message.reply_text("❌ حساب همکار فعال پیدا نشد. دوباره شماره را وارد کنید.",reply_markup=_cancel_kb(B,st.get("lang","fa"))); raise ApplicationHandlerStop
        from core import check_password
        try: ok=bool(check_password(t,row["password_hash"]))
        except Exception: ok=False
        if not ok:
            await update.effective_message.reply_text("❌ رمز ورود نادرست است.\n\n🔐 رمز را دوباره وارد کنید:",reply_markup=_cancel_kb(B,st.get("lang","fa"))); raise ApplicationHandlerStop
        st.update(partner_id=row["id"],partner_active=True,partner_logged_out=False,mode=None,step=None,partner=row["phone"],partner_phone=row["phone"])
        try: B.db.set_setting("partner_chat_"+str(row["id"]),str(uid))
        except Exception: pass
        return await B._partner_registration_old(update,context)

async def callback(update,context,B):
    q=update.callback_query
    if not q or not str(q.data or "").startswith("partnerreg:"): return
    await q.answer()
    action=str(q.data).split(":",1)[1]
    if action=="request": return await _request_begin(update,context,B)
    if action=="cancel":
        st=B.S.setdefault(q.from_user.id,{}); st.update(mode=None,step=None,partner_pending=False)
        await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=B.main(q.from_user.id)); raise ApplicationHandlerStop
    if action=="track":
        B.S.setdefault(q.from_user.id,{})["mode"]="partner_req_track"
        await q.message.reply_text("🎫 کد پیگیری درخواست عضویت را وارد کنید:",reply_markup=_cancel_kb(B)); raise ApplicationHandlerStop
    raise ApplicationHandlerStop

async def decision(update,context,B):
    q=update.callback_query
    if not q or not str(q.data or "").startswith("partnerreq:"): return
    await q.answer()
    uid=q.from_user.id
    if not B.admin(uid):
        await q.message.reply_text("⛔ این بخش فقط برای مدیریت فعال است."); raise ApplicationHandlerStop
    parts=str(q.data).split(":")
    if len(parts)!=3: raise ApplicationHandlerStop
    try: rid=int(parts[2])
    except Exception:
        await q.message.reply_text("❌ شناسه درخواست نامعتبر است."); raise ApplicationHandlerStop
    row=B.db.conn.execute("SELECT * FROM partner_requests WHERE id=?",(rid,)).fetchone()
    if not row:
        await q.message.reply_text("❌ درخواست عضویت پیدا نشد."); raise ApplicationHandlerStop
    if row["status"]!="pending":
        await q.message.reply_text("ℹ️ این درخواست قبلاً بررسی شده است."); raise ApplicationHandlerStop
    now=B.now(); approved=parts[1]=="approve"
    if parts[1] not in {"approve","reject"}: raise ApplicationHandlerStop
    B.db.conn.execute("UPDATE partners SET active=?,updated_at=? WHERE id=?",(1 if approved else 0,now,row["partner_id"]))
    B.db.conn.execute("UPDATE partner_requests SET status=?,reviewed_at=?,reviewer_id=? WHERE id=?",( "approved" if approved else "rejected",now,str(uid),rid))
    B.db.conn.commit()
    result=("✅ درخواست عضویت تأیید شد.\n\nحساب همکار فعال شد." if approved else "❌ درخواست عضویت رد شد.")
    try: await context.bot.send_message(chat_id=int(row["telegram_user_id"]),text=result+"\n\n🎫 کد پیگیری: "+str(row["tracking_code"]))
    except Exception: log.exception("membership result notification failed")
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await q.message.reply_text(result); raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,MARK,False): return True
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_user_id TEXT NOT NULL,
        platform TEXT DEFAULT 'telegram', partner_id INTEGER, phone TEXT NOT NULL,
        name TEXT NOT NULL, status TEXT DEFAULT 'pending', tracking_code TEXT UNIQUE,
        created_at TEXT, reviewed_at TEXT, reviewer_id TEXT DEFAULT '', note TEXT DEFAULT '')""")
    B.db.conn.commit()
    B._partner_registration_old=getattr(B,"partner",None)
    # Final partner keyboard owner: every visible button has a stable label route.
    try:
        import telegram_ui_policy_v2 as UI
        def _partner_kb(lang="fa"):
            uid = int(UI._uid() or 0)
            return UI.inline([
                ["🟢 ➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
                ["📱 خدمات سیم کارت", "🪪 فیدای غیر حضوری"],
                ["🔎 پیگیری کد", "📋 سوابق"],
                ["💰 موجودی", "🎫 تیکت به مدیریت"],
                ["🚪 خروج از پنل"],
                ["❌ انصراف"],
            ], B, uid)
        B.partner_kb = _partner_kb
    except Exception:
        log.exception("canonical partner keyboard owner unavailable")
    async def partner_wrapper(update,context): return await partner_entry(update,context,B)
    B.partner=partner_wrapper
    # This is the canonical text owner and intentionally runs before all legacy
    # partner phone/password handlers, but after the absolute off-hours firewall.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:text(u,c,B)),group=-10000000)
    app.add_handler(CallbackQueryHandler(lambda u,c:callback(u,c,B),pattern=r"^partnerreg:"),group=-5002)
    app.add_handler(CallbackQueryHandler(lambda u,c:decision(u,c,B),pattern=r"^partnerreq:"),group=-5001)
    setattr(B,MARK,True)
    log.info("Canonical partner authentication/membership owner v4 installed")
    return True
