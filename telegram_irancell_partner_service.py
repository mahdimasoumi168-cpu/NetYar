"""Telegram partner-only Irancell SIM service."""
import logging, re, secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.irancell_partner")
PRICE = 980_000
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
        [InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"irsim:last:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"irsim:detail:{rid}")],
        [InlineKeyboardButton("✅ تأیید درخواست", callback_data=f"irsim:approve:{rid}"), InlineKeyboardButton("❌ رد درخواست", callback_data=f"irsim:reject:{rid}")],
        [InlineKeyboardButton("🔐 درخواست کد امنیتی", callback_data=f"panel:askcode:{rid}")],
    ])

def _ensure_service(B):
    try:
        B.db.conn.execute("INSERT OR IGNORE INTO services(key,name,description,price,active) VALUES(?,?,?,?,1)", (SERVICE_KEY, "حل مشکل سیم کارت ایرانسل", "حل مشکل سیم کارت ایرانسل از طریق پنل همکاران", PRICE))
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
            return old_partner_kb(lang)
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
                    return await update.callback_query.message.reply_text("📱 حل مشکل سیم کارت ایرانسل\n\nشماره موبایل ایرانسل که به نام مشترک ثبت شده است را وارد کنید:", reply_markup=BB.cancel_kb(st.get("lang", "fa")))
                return await old_dispatch(update, context, BB, label)
            U._dispatch = dispatch
            U._irancell_dispatch_wrapped = True
    except Exception:
        log.exception("Could not extend Telegram UI dispatcher")

    async def text(update, context):
        msg = update.effective_message
        if not msg or not update.effective_user: return
        uid = update.effective_user.id; st = B.S.setdefault(uid, {})
        if st.get("mode") != PHONE_MODE: return
        p = _phone(msg.text or "")
        if not p:
            await msg.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 لطفاً شماره ۱۱ رقمی ایرانسل را با ۰۹ وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        else:
            st.setdefault("irancell", {})["phone"] = p; st["mode"] = PHOTO_MODE
            await msg.reply_text("📸 حالا عکس مدرک شناسایی مشترک را ارسال کنید:\n\nمدرک باید واضح و خوانا باشد.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        raise ApplicationHandlerStop

    async def media(update, context):
        msg = update.effective_message
        if not msg or not update.effective_user: return
        uid = update.effective_user.id; st = B.S.setdefault(uid, {})
        if st.get("mode") != PHOTO_MODE: return
        fid = msg.photo[-1].file_id if getattr(msg, "photo", None) else (msg.document.file_id if getattr(msg, "document", None) else "")
        if not fid:
            await msg.reply_text("❌ لطفاً عکس یا فایل مدرک شناسایی را ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop
        s = st.setdefault("irancell", {}); phone = s.get("phone", ""); pid = st.get("partner_id")
        if not pid or not phone:
            st["mode"] = None; await msg.reply_text("❌ نشست خدمت منقضی شده است. دوباره از پنل همکاران وارد شوید.", reply_markup=B.partner_kb(st.get("lang", "fa"))); raise ApplicationHandlerStop
        conn = B.db.conn
        try:
            conn.execute("BEGIN IMMEDIATE")
            p = conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (int(pid),)).fetchone()
            if not p: raise RuntimeError("partner_not_found")
            if int(p["balance"] or 0) < PRICE:
                conn.rollback(); st["mode"] = None
                await msg.reply_text(f"❌ اعتبار پنل همکار کافی نیست.\n\n💳 اعتبار فعلی: {int(p['balance'] or 0):,} تومان\n💰 هزینه خدمت: {PRICE:,} تومان\n\nابتدا حساب پنل را شارژ کنید.", reply_markup=B.partner_kb(st.get("lang", "fa"))); raise ApplicationHandlerStop
            user_id = B.db.user("telegram", uid, update.effective_user.username or "", update.effective_user.full_name or "")
            cur = conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?", (PRICE, B.now(), int(pid), PRICE))
            if cur.rowcount != 1: raise RuntimeError("insufficient_balance")
            code = "NYM-" + secrets.token_hex(4).upper()
            cur = conn.execute("INSERT INTO requests(tracking_code,user_id,service_key,platform,status,amount,payment_status,payment_method,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (code,user_id,SERVICE_KEY,"telegram","submitted",PRICE,"paid","partner_balance",B.now(),B.now()))
            rid = cur.lastrowid
            conn.execute("CREATE TABLE IF NOT EXISTS request_files (id INTEGER PRIMARY KEY AUTOINCREMENT,request_id INTEGER,file_id TEXT,file_type TEXT,caption TEXT,created_at TEXT)")
            conn.execute("INSERT INTO request_files(request_id,file_id,file_type,caption,created_at) VALUES(?,?,?,?,?)", (rid,fid,"document","مدرک شناسایی سیم کارت ایرانسل",B.now()))
            conn.commit()
        except ApplicationHandlerStop:
            raise
        except Exception:
            try: conn.rollback()
            except Exception: pass
            log.exception("Irancell service failed")
            await msg.reply_text("❌ ثبت خدمت انجام نشد و مبلغی از شارژ شما کسر نشد. دوباره تلاش کنید.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop
        st["mode"] = "partner"
        st.pop("irancell", None)
        admin_ids = list(getattr(B, "ADM", ()) or getattr(B, "ADMINS", ()) or [])
        text = f"📱 درخواست حل مشکل سیم کارت ایرانسل\n\n🆔 کد پیگیری: {code}\n👤 همکار: {p['phone'] or pid}\n📱 شماره ایرانسل مشترک: {phone}\n💰 هزینه: {PRICE:,} تومان\n💳 روش پرداخت: کسر از شارژ همکار"
        for aid in admin_ids:
            try:
                await context.bot.send_message(chat_id=int(aid), text=text, reply_markup=_admin_markup(rid))
                await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 مدرک درخواست {code}")
            except Exception:
                log.exception("Irancell admin notification failed")
        await msg.reply_text(f"✅ درخواست شما ثبت شد.\n\n🆔 کد پیگیری: {code}\n💰 مبلغ کسرشده از شارژ همکار: {PRICE:,} تومان", reply_markup=B.partner_kb(st.get("lang", "fa")))
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-9999999)
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.ALL), media), group=-9999998)
    app.add_handler(CallbackQueryHandler(lambda update, context: None, pattern=r"^__never__"), group=-9999997)
    B._irancell_partner_service = True
