"""Canonical Telegram partner registration and cooperation-request workflow.

New partners can create credentials, enter a limited partner area, submit a
cooperation request, receive a tracking code, and track the decision. Approval
activates the partner account; rejection leaves the account inactive so the
applicant can submit a new request later.
"""
import logging
import secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.partner_registration")


def _normalize_phone(B, value):
    fn = getattr(B, "normalize_phone", None)
    if fn:
        return fn(value)
    return str(value or "").strip()


def _limited_kb(B):
    return B.kb([["🤝 درخواست همکاری"], ["🎫 پیگیری درخواست همکاری"], ["🚪 خروج از پنل"]])


def _pending_kb(B):
    return B.kb([["🎫 پیگیری درخواست همکاری"], ["🤝 درخواست همکاری"], ["🚪 خروج از پنل"]])


def _tracking_code():
    return "NYC-" + secrets.token_hex(4).upper()


async def _show_limited(update, B, request_row=None):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if request_row:
        st["partner_request_id"] = request_row["id"]
        st["partner_pending"] = request_row["status"] == "pending"
    status = request_row["status"] if request_row else "pending"
    code = request_row["tracking_code"] if request_row else ""
    if status == "approved":
        text = "✅ درخواست همکاری شما تأیید شده است.\n\nاکنون می‌توانید وارد پنل کامل همکاران شوید."
        return await update.effective_message.reply_text(text, reply_markup=B.partner_kb(st.get("lang", "fa")))
    if status == "rejected":
        text = f"❌ درخواست همکاری شما رد شده است.\n\n🎫 کد پیگیری: {code}\n\nمی‌توانید وضعیت را با گزینه «🎫 پیگیری درخواست همکاری» بررسی کنید یا دوباره درخواست همکاری بدهید."
    elif code:
        text = f"⏳ درخواست همکاری شما در حال بررسی است.\n\n🎫 کد پیگیری: {code}\n\nپس از بررسی مدیریت، نتیجه برای شما ارسال می‌شود."
    else:
        text = "👥 پنل همکاران جدید\n\nفعلاً فقط گزینه «🤝 درخواست همکاری» برای شما فعال است."
    return await update.effective_message.reply_text(text, reply_markup=_pending_kb(B) if code else _limited_kb(B))


async def partner_entry(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("partner_id") and st.get("partner_active", True):
        return None
    # A previously created pending request belongs to this Telegram user.
    row = B.db.conn.execute(
        "SELECT * FROM partner_requests WHERE telegram_user_id=? ORDER BY id DESC LIMIT 1", (str(uid),)
    ).fetchone()
    if row and row["status"] in {"pending", "approved"}:
        if row["status"] == "approved":
            p = B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1", (row["phone"],)).fetchone()
            if p:
                st.update(partner_id=p["id"], partner_active=True, mode=None)
                return await B.partner(update, context)
        return await _show_limited(update, B, row)
    st["mode"] = "partner_entry_phone"
    return await update.effective_message.reply_text(
        "📱 شماره موبایل همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa"))
    )


async def text(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    t = (update.effective_message.text or "").strip()
    if mode == "partner_entry_phone":
        phone = _normalize_phone(B, t)
        if not phone:
            return await update.effective_message.reply_text("❌ شماره موبایل معتبر نیست.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        active = B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1", (phone,)).fetchone()
        if active:
            st.update(phone=phone, mode="partner_entry_pass")
            return await update.effective_message.reply_text("🔐 رمز عبور را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        row = B.db.conn.execute(
            "SELECT * FROM partner_requests WHERE phone=? AND telegram_user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
            (phone, str(uid)),
        ).fetchone()
        if row:
            return await _show_limited(update, B, row)
        st.update(phone=phone, mode="partner_reg_pass")
        return await update.effective_message.reply_text(
            "🔐 رمز جدید خود را وارد کنید:\n\nاین رمز را برای ورودهای بعدی به پنل همکاران حفظ کنید.",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )
    if mode == "partner_entry_pass":
        p = B.db.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1", (st.get("phone"),)).fetchone()
        if not p or not B.check_password(t, p["password_hash"]):
            return await update.effective_message.reply_text("❌ اطلاعات ورود نادرست است.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        st.update(partner_id=p["id"], partner_active=True, mode=None)
        return await B.partner(update, context)
    if mode == "partner_reg_pass":
        if len(t) < 4:
            return await update.effective_message.reply_text("❌ رمز باید حداقل ۴ رقم/حرف باشد.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        st["partner_password"] = t
        st["mode"] = "partner_reg_name"
        return await update.effective_message.reply_text(
            "👤 نام همکار یا نام مجموعه را وارد کنید.\n\nمثال: کافی نت مهیار اصفهان",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )
    if mode == "partner_reg_name":
        name = t[:120]
        if len(name) < 2:
            return await update.effective_message.reply_text("❌ نام همکار/مجموعه را وارد کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        phone = st.get("phone")
        existing = B.db.conn.execute("SELECT id FROM partners WHERE phone=?", (phone,)).fetchone()
        if existing:
            return await update.effective_message.reply_text("❌ این شماره قبلاً ثبت شده است. لطفاً از پنل همکاران وارد شوید.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        from core import hash_password
        password_hash = hash_password(st.get("partner_password", ""))
        code = _tracking_code()
        cur = B.db.conn.execute(
            "INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (phone, password_hash, name, 0, 0, B.now(), B.now()),
        )
        partner_id = cur.lastrowid
        cur = B.db.conn.execute(
            "INSERT INTO partner_requests(telegram_user_id,platform,partner_id,phone,name,status,tracking_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (str(uid), "telegram", partner_id, phone, name, "pending", code, B.now()),
        )
        req_id = cur.lastrowid
        B.db.conn.commit()
        st.update(partner_id=partner_id, partner_request_id=req_id, partner_pending=True, partner_active=False, mode=None)
        mk = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تأیید درخواست همکاری", callback_data=f"partnerreq:approve:{req_id}"),
             InlineKeyboardButton("❌ رد درخواست همکاری", callback_data=f"partnerreq:reject:{req_id}")]
        ])
        msg = f"🤝 درخواست همکاری جدید\n\n👤 نام/مجموعه: {name}\n📱 موبایل: {phone}\n🎫 کد پیگیری: {code}\n🆔 شناسه درخواست: {req_id}"
        for aid in B.ADM:
            try:
                await context.bot.send_message(chat_id=int(aid), text=msg, reply_markup=mk)
            except Exception:
                log.exception("partner cooperation admin notification failed")
        return await update.effective_message.reply_text(
            f"✅ درخواست همکاری شما ثبت شد.\n\n🎫 کد پیگیری: {code}\n\nدرخواست برای مدیریت ارسال شد. پس از تأیید یا رد، نتیجه برای شما ارسال می‌شود.",
            reply_markup=_pending_kb(B),
        )
    if mode == "partner_req_track":
        row = B.db.conn.execute(
            "SELECT * FROM partner_requests WHERE telegram_user_id=? AND tracking_code=? ORDER BY id DESC LIMIT 1",
            (str(uid), t.upper()),
        ).fetchone()
        if not row:
            return await update.effective_message.reply_text("❌ کد پیگیری پیدا نشد.", reply_markup=_pending_kb(B))
        return await _show_limited(update, B, row)
    return None


async def click(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("partnerreq:"):
        return
    await q.answer()
    uid = q.from_user.id
    if not B.admin(uid):
        await q.message.reply_text("⛔ این بخش فقط برای مدیریت فعال است.")
        raise ApplicationHandlerStop
    parts = str(q.data).split(":")
    action = parts[1] if len(parts) > 1 else ""
    try:
        req_id = int(parts[2])
    except Exception:
        await q.message.reply_text("❌ درخواست نامعتبر است.")
        raise ApplicationHandlerStop
    row = B.db.conn.execute("SELECT * FROM partner_requests WHERE id=?", (req_id,)).fetchone()
    if not row:
        await q.message.reply_text("❌ درخواست همکاری پیدا نشد.")
        raise ApplicationHandlerStop
    if row["status"] != "pending":
        await q.message.reply_text(f"ℹ️ این درخواست قبلاً بررسی شده است. وضعیت: {row['status']}")
        raise ApplicationHandlerStop
    if action == "approve":
        B.db.conn.execute("UPDATE partners SET active=1,updated_at=? WHERE id=?", (B.now(), row["partner_id"]))
        B.db.conn.execute("UPDATE partner_requests SET status='approved',reviewed_at=?,reviewer_id=? WHERE id=?", (B.now(), str(uid), req_id))
        B.db.conn.commit()
        result = f"✅ درخواست همکاری تأیید شد.\n\n🎫 کد پیگیری: {row['tracking_code']}\n\nحساب همکار فعال شد."
    elif action == "reject":
        B.db.conn.execute("UPDATE partner_requests SET status='rejected',reviewed_at=?,reviewer_id=? WHERE id=?", (B.now(), str(uid), req_id))
        B.db.conn.commit()
        result = f"❌ درخواست همکاری رد شد.\n\n🎫 کد پیگیری: {row['tracking_code']}"
    else:
        await q.message.reply_text("❌ عملیات نامعتبر است.")
        raise ApplicationHandlerStop
    try:
        await context.bot.send_message(chat_id=int(row["telegram_user_id"]), text=result + "\n\nبرای مشاهده وضعیت، گزینه «🎫 پیگیری درخواست همکاری» را بزنید.")
    except Exception:
        log.exception("partner decision notification failed")
    await q.message.edit_reply_markup(reply_markup=None)
    await q.message.reply_text(result)
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_partner_registration_v2", False):
        return
    # Ensure the request table exists without changing existing partner data.
    B.db.conn.execute("""
        CREATE TABLE IF NOT EXISTS partner_requests(
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
        )
    """)
    B.db.conn.commit()
    B.check_password = __import__("core").check_password
    old_partner = B.partner

    async def partner_wrapper(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("partner_id") and st.get("partner_active", True):
            return await old_partner(update, context)
        return await partner_entry(update, context, B)

    B.partner = partner_wrapper
    app.add_handler(CallbackQueryHandler(lambda u, c: click(u, c, B), pattern=r"^partnerreq:"), group=-4100)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: text(u, c, B), group=-3600))
    B._partner_registration_v2 = True
    log.info("Partner registration/cooperation workflow installed")
