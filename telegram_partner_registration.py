"""Canonical Telegram partner onboarding: phone -> existing login OR new membership request."""
import logging, re, secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.partner_registration_v3")
MARK = "_partner_registration_v3"

def _phone(B, value):
    fn = getattr(B, "normalize_phone", None)
    if callable(fn):
        try:
            p = fn(value)
            if p:
                return p
        except Exception:
            pass
    p = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
    p = re.sub(r"\D", "", p)
    if p.startswith("98"):
        p = "0" + p[2:]
    return p if re.fullmatch(r"09\d{9}", p) else ""

def _cancel_kb(B, lang="fa"):
    try:
        return B.cancel_kb(lang)
    except Exception:
        from telegram import ReplyKeyboardMarkup
        return ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True)

def _new_member_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🤝 درخواست عضویت", callback_data="partnerreg:request"),
        InlineKeyboardButton("❌ انصراف", callback_data="partnerreg:cancel"),
    ]])

def _pending_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🎫 پیگیری درخواست", callback_data="partnerreg:track"),
    ],[
        InlineKeyboardButton("❌ انصراف", callback_data="partnerreg:cancel"),
    ]])

def _code():
    return "NYC-" + secrets.token_hex(4).upper()

async def _new_member(update, B):
    await update.effective_message.reply_text(
        "👤 شما عضو جدید می‌باشید.\n\n"
        "برای عضویت و دریافت پنل همکاران، دکمه «🤝 درخواست عضویت» را بزنید.",
        reply_markup=_new_member_kb(),
    )

async def _status(update, B, row):
    status = str(row["status"] or "")
    if status == "approved":
        try:
            B.db.conn.execute("UPDATE partners SET active=1,updated_at=? WHERE id=?", (B.now(), row["partner_id"]))
            B.db.conn.commit()
        except Exception:
            pass
        st = B.S.setdefault(update.effective_user.id, {})
        st.update(partner_id=row["partner_id"], partner_active=True, mode=None, partner_logged_out=False)
        return await update.effective_message.reply_text(
            "✅ درخواست عضویت شما تأیید شده است.\n\n"
            "اکنون می‌توانید با رمز تعیین‌شده وارد پنل همکاران شوید.",
            reply_markup=B.partner_kb(st.get("lang","fa")),
        )
    if status == "rejected":
        return await update.effective_message.reply_text(
            f"❌ درخواست عضویت شما رد شده است.\n\n🎫 کد پیگیری: {row['tracking_code']}\n\n"
            "در صورت تمایل می‌توانید دوباره درخواست عضویت ثبت کنید.",
            reply_markup=_new_member_kb(),
        )
    return await update.effective_message.reply_text(
        f"⏳ درخواست عضویت شما در حال بررسی مدیریت است.\n\n"
        f"🎫 کد پیگیری: {row['tracking_code']}\n\n"
        "حداکثر تا ۲۴ ساعت نتیجه تأیید یا رد درخواست برای شما ارسال می‌شود.",
        reply_markup=_pending_kb(),
    )

async def partner_entry(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    # An already authenticated partner enters the real partner panel.
    if st.get("partner_id") and st.get("partner_active", False) and not st.get("partner_logged_out"):
        return await B._partner_registration_old(update, context)

    st.pop("partner_pending", None)
    st["mode"] = "partner_entry_phone"
    await update.effective_message.reply_text(
        "👥 پنل همکاران\n\n📱 شماره موبایل همکار را وارد کنید:",
        reply_markup=_cancel_kb(B, st.get("lang","fa")),
    )

async def _request_begin(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    phone = st.get("phone")
    if not phone:
        await update.effective_message.reply_text("❌ ابتدا شماره موبایل را وارد کنید.")
        return
    row = B.db.conn.execute("SELECT * FROM partners WHERE phone=? LIMIT 1", (phone,)).fetchone()
    if row and int(row["active"] or 0) == 1:
        st["mode"] = "partner_entry_pass"
        return await update.effective_message.reply_text("🔐 این شماره عضو است. رمز ورود را وارد کنید:", reply_markup=_cancel_kb(B, st.get("lang","fa")))
    if row:
        req = B.db.conn.execute(
            "SELECT * FROM partner_requests WHERE partner_id=? ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        if req and req["status"] == "pending":
            st.update(partner_id=row["id"], partner_active=False, partner_pending=True)
            return await _status(update, B, req)
        st.update(partner_id=row["id"], partner_active=False, mode="partner_reg_pass")
        return await update.effective_message.reply_text(
            "🔐 ابتدا یک رمز ورود برای پنل خود تعیین کنید (حداقل ۴ کاراکتر):",
            reply_markup=_cancel_kb(B, st.get("lang","fa")),
        )
    st["mode"] = "partner_reg_pass"
    await update.effective_message.reply_text(
        "🔐 ابتدا یک رمز ورود برای پنل خود تعیین کنید (حداقل ۴ کاراکتر):",
        reply_markup=_cancel_kb(B, st.get("lang","fa")),
    )

async def _create_request(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    phone = st.get("phone")
    name = (st.get("partner_reg_name") or "").strip()[:120]
    password = st.get("partner_password") or ""
    if not phone or len(password) < 4 or len(name) < 2:
        await update.effective_message.reply_text("❌ اطلاعات عضویت ناقص است. دوباره درخواست عضویت را شروع کنید.", reply_markup=_new_member_kb())
        return
    from core import hash_password
    now = B.now()
    row = B.db.conn.execute("SELECT * FROM partners WHERE phone=? LIMIT 1", (phone,)).fetchone()
    if row:
        pid = row["id"]
        if int(row["active"] or 0) == 1:
            st["mode"] = "partner_entry_pass"
            return await update.effective_message.reply_text("🔐 این شماره عضو است. رمز ورود را وارد کنید:", reply_markup=_cancel_kb(B, st.get("lang","fa")))
        B.db.conn.execute(
            "UPDATE partners SET password_hash=?,name=?,updated_at=? WHERE id=?",
            (hash_password(password), name, now, pid),
        )
    else:
        cur = B.db.conn.execute(
            "INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (phone, hash_password(password), name, 0, 0, now, now),
        )
        pid = cur.lastrowid
    # Only one pending application per partner.
    old = B.db.conn.execute(
        "SELECT * FROM partner_requests WHERE partner_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
        (pid,),
    ).fetchone()
    if old:
        st.update(partner_id=pid, partner_pending=True, mode=None)
        return await _status(update, B, old)
    code = _code()
    cur = B.db.conn.execute(
        "INSERT INTO partner_requests(telegram_user_id,platform,partner_id,phone,name,status,tracking_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (str(uid), "telegram", pid, phone, name, "pending", code, now),
    )
    rid = cur.lastrowid
    B.db.conn.commit()
    st.update(partner_id=pid, partner_active=False, partner_pending=True, partner_request_id=rid, mode=None)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تأیید عضویت", callback_data=f"partnerreq:approve:{rid}"),
        InlineKeyboardButton("❌ رد عضویت", callback_data=f"partnerreq:reject:{rid}"),
    ]])
    admin_ids = getattr(B, "ADM", []) or []
    msg = (
        "🤝 درخواست عضویت همکار جدید\n\n"
        f"👤 نام: {name}\n"
        f"📱 شماره موبایل: {phone}\n"
        f"🆔 شناسه درخواست: {rid}\n"
        f"🎫 کد پیگیری: {code}\n\n"
        "⏳ متقاضی اعلام شده که نتیجه حداکثر تا ۲۴ ساعت ارسال می‌شود."
    )
    for aid in admin_ids:
        try:
            await context.bot.send_message(chat_id=int(aid), text=msg, reply_markup=markup)
        except Exception:
            log.exception("partner membership admin notification failed")
    await update.effective_message.reply_text(
        "✅ درخواست عضویت شما با موفقیت ثبت شد.\n\n"
        f"🎫 کد پیگیری: {code}\n\n"
        "درخواست برای مدیریت ارسال شد. نتیجه تأیید یا رد حداکثر تا ۲۴ ساعت برای شما ارسال می‌شود.",
        reply_markup=_pending_kb(),
    )

async def text(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    t = (update.effective_message.text or "").strip()
    if t in {"❌ انصراف", "انصراف", "لغو"}:
        if mode and (mode.startswith("partner_") or mode == "partner_req_track"):
            for k in ("mode","partner_password","partner_reg_name","partner_pending","partner_request_id"):
                st.pop(k, None)
            await update.effective_message.reply_text("❌ عملیات عضویت/ورود لغو شد.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop
    if mode == "partner_entry_phone":
        phone = _phone(B, t)
        if not phone:
            return await update.effective_message.reply_text("❌ شماره موبایل معتبر نیست.", reply_markup=_cancel_kb(B, st.get("lang","fa")))
        st["phone"] = phone
        row = B.db.conn.execute("SELECT * FROM partners WHERE phone=? LIMIT 1", (phone,)).fetchone()
        if row and int(row["active"] or 0) == 1:
            st["mode"] = "partner_entry_pass"
            return await update.effective_message.reply_text("🔐 رمز ورود را وارد کنید:", reply_markup=_cancel_kb(B, st.get("lang","fa")))
        if row:
            req = B.db.conn.execute("SELECT * FROM partner_requests WHERE partner_id=? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
            st.update(partner_id=row["id"], partner_active=False)
            if req and req["status"] == "pending":
                st["mode"] = None
                return await _status(update, B, req)
        st["mode"] = "partner_new_wait"
        return await _new_member(update, B)
    if mode == "partner_new_wait":
        return await update.effective_message.reply_text("ℹ️ برای ادامه، ابتدا دکمه «🤝 درخواست عضویت» را بزنید.", reply_markup=_new_member_kb())
    if mode == "partner_reg_pass":
        if len(t) < 4:
            return await update.effective_message.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.", reply_markup=_cancel_kb(B, st.get("lang","fa")))
        st.update(partner_password=t, mode="partner_reg_name")
        return await update.effective_message.reply_text("👤 نام و نام خانوادگی یا نام مجموعه را وارد کنید:", reply_markup=_cancel_kb(B, st.get("lang","fa")))
    if mode == "partner_reg_name":
        if len(t) < 2:
            return await update.effective_message.reply_text("❌ نام معتبر وارد کنید.", reply_markup=_cancel_kb(B, st.get("lang","fa")))
        st.update(partner_reg_name=t[:120])
        return await _create_request(update, context, B)
    if mode == "partner_entry_pass":
        p = B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1 LIMIT 1", (st.get("phone"),)).fetchone()
        if not p:
            st["mode"] = "partner_entry_phone"
            return await update.effective_message.reply_text("❌ حساب عضو پیدا نشد. دوباره شماره را وارد کنید.")
        try:
            ok = bool(B.check_password(t, p["password_hash"]))
        except Exception:
            ok = False
        if not ok:
            return await update.effective_message.reply_text("❌ رمز ورود نادرست است.", reply_markup=_cancel_kb(B, st.get("lang","fa")))
        st.update(partner_id=p["id"], partner_active=True, partner_logged_out=False, mode=None)
        return await B._partner_registration_old(update, context)
    return None

async def callback(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("partnerreg:"):
        return
    await q.answer()
    action = str(q.data).split(":", 1)[1]
    if action == "request":
        return await _request_begin(update, context, B)
    if action == "cancel":
        uid = q.from_user.id
        B.S.setdefault(uid, {}).update(mode=None, partner_pending=False)
        await q.message.reply_text("❌ عملیات لغو شد.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    if action == "track":
        uid = q.from_user.id
        B.S.setdefault(uid, {})["mode"] = "partner_req_track"
        await q.message.reply_text("🎫 کد پیگیری درخواست عضویت را وارد کنید:", reply_markup=_cancel_kb(B))
        raise ApplicationHandlerStop
    raise ApplicationHandlerStop

async def decision(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("partnerreq:"):
        return
    await q.answer()
    uid = q.from_user.id
    if not B.admin(uid):
        await q.message.reply_text("⛔ این بخش فقط برای مدیریت فعال است.")
        raise ApplicationHandlerStop
    parts = str(q.data).split(":")
    if len(parts) != 3:
        await q.message.reply_text("❌ عملیات نامعتبر است.")
        raise ApplicationHandlerStop
    try:
        rid = int(parts[2])
    except Exception:
        await q.message.reply_text("❌ شناسه درخواست نامعتبر است.")
        raise ApplicationHandlerStop
    row = B.db.conn.execute("SELECT * FROM partner_requests WHERE id=?", (rid,)).fetchone()
    if not row:
        await q.message.reply_text("❌ درخواست عضویت پیدا نشد.")
        raise ApplicationHandlerStop
    if row["status"] != "pending":
        await q.message.reply_text(f"ℹ️ این درخواست قبلاً بررسی شده است: {row['status']}")
        raise ApplicationHandlerStop
    now = B.now()
    if parts[1] == "approve":
        B.db.conn.execute("UPDATE partners SET active=1,updated_at=? WHERE id=?", (now, row["partner_id"]))
        status_text = "approved"
        result = f"✅ درخواست عضویت تأیید شد.\n\n👤 {row['name']}\n📱 {row['phone']}\n🎫 {row['tracking_code']}\n\nحساب همکار فعال شد."
    elif parts[1] == "reject":
        B.db.conn.execute("UPDATE partners SET active=0,updated_at=? WHERE id=?", (now, row["partner_id"]))
        status_text = "rejected"
        result = f"❌ درخواست عضویت رد شد.\n\n👤 {row['name']}\n📱 {row['phone']}\n🎫 {row['tracking_code']}"
    else:
        await q.message.reply_text("❌ عملیات نامعتبر است.")
        raise ApplicationHandlerStop
    B.db.conn.execute(
        "UPDATE partner_requests SET status=?,reviewed_at=?,reviewer_id=? WHERE id=?",
        (status_text, now, str(uid), rid),
    )
    B.db.conn.commit()
    try:
        await context.bot.send_message(
            chat_id=int(row["telegram_user_id"]),
            text=result + "\n\nبرای ورود دوباره به پنل همکاران، شماره موبایل و رمز خود را وارد کنید.",
        )
    except Exception:
        log.exception("partner membership decision notification failed")
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await q.message.reply_text(result)
    raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, MARK, False):
        return True
    B.db.conn.execute(
        """CREATE TABLE IF NOT EXISTS partner_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id TEXT NOT NULL,
            platform TEXT DEFAULT 'telegram',
            partner_id INTEGER,
            phone TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            tracking_code TEXT UNIQUE,
            created_at TEXT,
            reviewed_at TEXT,
            reviewer_id TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )"""
    )
    B.db.conn.commit()
    try:
        B.check_password = __import__("core").check_password
    except Exception:
        pass
    B._partner_registration_old = B.partner
    async def partner_wrapper(update, context):
        return await partner_entry(update, context, B)
    B.partner = partner_wrapper
    app.add_handler(CallbackQueryHandler(lambda u,c: callback(u,c,B), pattern=r"^partnerreg:"), group=-5002)
    app.add_handler(CallbackQueryHandler(lambda u,c: decision(u,c,B), pattern=r"^partnerreq:"), group=-5001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: text(u,c,B)), group=-3600)
    log.info("Canonical partner membership onboarding v3 installed")
    setattr(B, MARK, True)
    return True
