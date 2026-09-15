"""Partner-only Irancell SIM ownership/problem service.

Flow: partner panel -> subscriber Irancell mobile -> identity document photo ->
970,000 toman debit from partner balance -> request + full admin notification.
The debit and request creation are atomic so a failed request never consumes credit.
"""
import logging, re, secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.irancell_partner")
PRICE = 970_000
SERVICE_KEY = "irancell_sim_issue"
BTN = "📱 حل مشکل سیم کارت ایرانسل"
PHONE_MODE = "irancell_partner_phone"
PHOTO_MODE = "irancell_partner_document"


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))


def _phone(v):
    s = re.sub(r"[\s\-()]+", "", _digits(v).strip())
    if s.startswith("+98"): s = "0" + s[3:]
    elif s.startswith("0098"): s = "0" + s[4:]
    return s if re.fullmatch(r"09\d{9}", s) else None


def _admin_markup(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"irsim:detail:{rid}")],
        [InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"irsim:review:{rid}"), InlineKeyboardButton("✅ انجام شد", callback_data=f"irsim:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"irsim:reject:{rid}")],
    ])


def _ensure_service(B):
    try:
        B.db.conn.execute(
            "INSERT OR IGNORE INTO services(key,name,description,price,active) VALUES(?,?,?,?,1)",
            (SERVICE_KEY, BTN.replace("📱 ", ""), "حل مشکل سیم کارت ایرانسل از طریق پنل همکاران", PRICE),
        )
        B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) SELECT 'price_irancell_sim', ? WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key='price_irancell_sim')", (str(PRICE),))
        # Keep the service price correct even if the service was already created with the old price.
        B.db.conn.execute("UPDATE services SET price=?, active=1, description=? WHERE key=?", (PRICE, "حل مشکل سیم کارت ایرانسل از طریق پنل همکاران", SERVICE_KEY))
        B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('price_irancell_sim',?)", (str(PRICE),))
        B.db.conn.commit()
    except Exception:
        log.exception("Could not register Irancell service")


def install(app, B):
    if getattr(B, "_irancell_partner_service", False): return
    _ensure_service(B)

    old_partner_kb = B.partner_kb
    def partner_kb(lang="fa"):
        kb = old_partner_kb(lang)
        try:
            import telegram_ui_policy_v2 as U
            return U.inline([
                ["➕ شارژ حساب", BTN],
                ["🏛 حل مشکل سامانه دولت من", "🎫 درخواست‌های من"],
                ["🔎 پیگیری کد", "📋 سوابق"],
                ["💰 موجودی"],
                ["✉️ ارسال تیکت به مدیریت"],
                ["🚪 خروج از پنل"],
                ["🔄 شروع مجدد"],
            ], B)
        except Exception:
            return kb
    B.partner_kb = partner_kb

    try:
        import telegram_ui_policy_v2 as U
        old_dispatch = U._dispatch
        if not getattr(U, "_irancell_dispatch_wrapped", False):
            async def dispatch(update, context, BB, label):
                if label == BTN:
                    uid = update.callback_query.from_user.id
                    st = BB.S.setdefault(uid, {})
                    if not st.get("partner_id") or not st.get("partner_active", True):
                        return await update.callback_query.message.reply_text("❌ ابتدا وارد پنل همکاران شوید.", reply_markup=BB.main(uid))
                    st["mode"] = PHONE_MODE
                    st.pop("irancell", None)
                    return await update.callback_query.message.reply_text(
                        "📱 حل مشکل سیم کارت ایرانسل\n\nشماره موبایل ایرانسل که به نام مشترک ثبت شده است را وارد کنید:",
                        reply_markup=BB.cancel_kb(st.get("lang", "fa")),
                    )
                return await old_dispatch(update, context, BB, label)
            U._dispatch = dispatch
            U._irancell_dispatch_wrapped = True
    except Exception:
        log.exception("Could not extend Telegram UI dispatcher")

    async def text(update, context):
        msg = update.effective_message
        if not msg or not update.effective_user: return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != PHONE_MODE: return
        p = _phone(msg.text or "")
        if not p:
            await msg.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 لطفاً شماره ۱۱ رقمی ایرانسل را با ۰۹ وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        else:
            st.setdefault("irancell", {})["phone"] = p
            st["mode"] = PHOTO_MODE
            await msg.reply_text("📸 حالا عکس مدرک شناسایی مشترک را ارسال کنید:\n\nمدرک باید واضح و خوانا باشد.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        raise ApplicationHandlerStop

    async def media(update, context):
        msg = update.effective_message
        if not msg or not update.effective_user: return
        uid = update.effective_user.id; st = B.S.setdefault(uid, {})
        if st.get("mode") != PHOTO_MODE: return
        fid = ""
        if getattr(msg, "photo", None): fid = msg.photo[-1].file_id
        elif getattr(msg, "document", None): fid = msg.document.file_id
        if not fid:
            await msg.reply_text("❌ لطفاً عکس یا فایل مدرک شناسایی را ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop

        s = st.setdefault("irancell", {})
        phone = s.get("phone", "")
        pid = st.get("partner_id")
        if not pid or not phone:
            st["mode"] = None
            await msg.reply_text("❌ نشست خدمت منقضی شده است. دوباره از پنل همکاران وارد شوید.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop

        conn = B.db.conn
        try:
            conn.execute("BEGIN IMMEDIATE")
            p = conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (int(pid),)).fetchone()
            if not p: raise RuntimeError("partner_not_found")
            balance = int(p["balance"] or 0)
            if balance < PRICE:
                conn.rollback(); st["mode"] = None
                await msg.reply_text(
                    f"❌ اعتبار پنل همکار کافی نیست.\n\n💳 اعتبار فعلی: {balance:,} تومان\n💰 هزینه خدمت: {PRICE:,} تومان\n\nابتدا حساب پنل را شارژ کنید.",
                    reply_markup=B.partner_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop

            user_id = B.db.user("telegram", uid, update.effective_user.username or "", update.effective_user.full_name or "")
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?",
                (PRICE, B.now(), int(pid), PRICE),
            )
            if cur.rowcount != 1: raise RuntimeError("insufficient_balance")
            code = "NYM-" + secrets.token_hex(4).upper()
            cur = conn.execute(
                "INSERT INTO requests(tracking_code,user_id,service_key,platform,status,amount,payment_status,payment_method,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (code, user_id, SERVICE_KEY, "telegram", "submitted", PRICE, "paid", "partner_balance", B.now(), B.now()),
            )
            rid = cur.lastrowid
            answers = {
                "partner_id": str(pid), "partner_name": str(p["name"] or ""), "partner_phone": str(p["phone"] or ""),
                "subscriber_phone": phone, "carrier": "ایرانسل", "service": "حل مشکل سیم کارت ایرانسل", "amount": str(PRICE),
            }
            for k, v in answers.items():
                conn.execute("INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)", (rid, k, v, "", B.now()))
            conn.execute("INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)", (rid, "identity_document", "", fid, B.now()))
            try:
                conn.execute("INSERT INTO audit_log(platform,actor_id,action,target,details,created_at) VALUES(?,?,?,?,?,?)", ("telegram", str(uid), "partner_irancell_service", str(rid), f"partner_id={pid};phone={phone};amount={PRICE}", B.now()))
            except Exception: pass
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass
            st["mode"] = None
            await msg.reply_text("❌ ثبت خدمت انجام نشد؛ هیچ مبلغی از اعتبار پنل کسر نشد. لطفاً دوباره تلاش کنید.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop

        text_admin = (
            "🆕 درخواست جدید از پنل همکاران\n\n"
            "📱 خدمت: حل مشکل سیم کارت ایرانسل\n"
            f"🎫 کد پیگیری: {code}\n"
            f"👤 نام همکار: {p['name'] or '-'}\n"
            f"📞 موبایل همکار: {p['phone'] or '-'}\n"
            f"📱 شماره موبایل مشترک ایرانسل: {phone}\n"
            "📄 مدرک شناسایی: پیوست شده\n"
            f"💰 مبلغ کسرشده از اعتبار پنل: {PRICE:,} تومان\n"
            "💳 وضعیت پرداخت: پرداخت‌شده از اعتبار پنل\n"
            "📌 وضعیت درخواست: در انتظار بررسی مدیریت"
        )
        for aid in B.ADM:
            try:
                await context.bot.send_message(chat_id=int(aid), text=text_admin, reply_markup=_admin_markup(rid))
                try: await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"📎 مدرک شناسایی مشترک\n🎫 {code}")
                except Exception: await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 مدرک شناسایی مشترک\n🎫 {code}")
            except Exception: log.exception("Irancell admin notification failed")

        st["mode"] = None; st.pop("irancell", None)
        await msg.reply_text(
            f"✅ درخواست با موفقیت ثبت شد.\n\n📱 خدمت: حل مشکل سیم کارت ایرانسل\n🎫 کد پیگیری: {code}\n💰 مبلغ کسرشده از اعتبار پنل: {PRICE:,} تومان\n\n📨 اطلاعات کامل و تصویر مدرک برای مدیریت ارسال شد.",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
        raise ApplicationHandlerStop

    async def admin_cb(update, context):
        q = update.callback_query; data = str(q.data or "")
        if not data.startswith("irsim:"): return
        await q.answer()
        if not B.admin(q.from_user.id): return await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
        parts = data.split(":")
        try: rid = int(parts[2])
        except Exception: return await q.message.reply_text("❌ شناسه درخواست نامعتبر است.")
        row = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        if not row: return await q.message.reply_text("❌ درخواست پیدا نشد.")
        if parts[1] == "detail":
            ans = B.db.conn.execute("SELECT field_key,answer FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
            body = [f"📋 جزئیات درخواست {row['tracking_code']}", "", "📱 خدمت: حل مشکل سیم کارت ایرانسل", f"💰 مبلغ: {int(row['amount'] or 0):,} تومان", f"💳 پرداخت: {row['payment_method'] or '-'}", f"📌 وضعیت: {row['status'] or '-'}"]
            for a in ans: body.append(f"• {a['field_key']}: {a['answer'] or '-'}")
            return await q.message.reply_text("\n".join(body), reply_markup=_admin_markup(rid))
        if parts[1] == "review":
            B.db.conn.execute("UPDATE requests SET status='reviewing',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            return await q.message.reply_text("⏳ درخواست به وضعیت «در حال بررسی» منتقل شد.", reply_markup=_admin_markup(rid))
        if parts[1] == "approve":
            B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            return await q.message.reply_text("✅ درخواست با موفقیت به وضعیت «انجام شد» منتقل شد.", reply_markup=_admin_markup(rid))
        if parts[1] == "reject":
            B.db.conn.execute("UPDATE requests SET status='rejected',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            return await q.message.reply_text("❌ درخواست رد شد.", reply_markup=_admin_markup(rid))

    app.add_handler(CallbackQueryHandler(admin_cb, pattern=r"^irsim:"), group=-6100)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, media), group=-6101)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-6102)
    B._irancell_partner_service = True
