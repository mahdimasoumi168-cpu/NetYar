"""Single authoritative Telegram admin UI and dispatcher.

This module is the final owner of the admin entry point and all ``adm:*``
callbacks. Legacy modules may provide business logic, but they do not own the
visible admin menu or its dispatch path.
"""
import os, re, inspect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

ADMIN_IDS = {"159039104", "7165912028"}
ADMIN_TEXTS = {"🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت", "🔵 🛠 پنل مدیریت بات", "🔵 🛠 پنل مدیریت"}


def _admin(B, uid):
    sid = str(uid); configured = set()
    for key in ("ADMIN_IDS", "ADMIN_ID_1", "ADMIN_ID_2", "TELEGRAM_ADMIN_IDS"):
        configured.update(x.strip() for x in re.split(r"[;,\s]+", os.getenv(key, "")) if x.strip())
    if sid in ADMIN_IDS or sid in configured: return True
    try: return bool(B.admin(uid))
    except Exception: return False


def menu():
    rows = [
        [("👤 کاربران", "adm:users"), ("👥 همکاران", "adm:partners")],
        [("➕ افزودن همکار", "adm:addpartner")],
        [("🌙 همکاران شب‌کار", "night2:menu")],
        [("🌙 بستن ربات در شب", "adm:night_off"), ("☀️ باز کردن ربات در شب", "adm:night_on")],
        [("📋 درخواست‌ها", "adm:requests"), ("💳 پرداخت‌ها", "adm:payments")],
        [("💰 شارژها", "adm:topups"), ("⚙️ قیمت‌ها", "adm:prices")],
        [("🟢 خدمات", "adm:services")],
        [("💵 افزایش شارژ", "adm:creditup"), ("💸 کاهش شارژ", "adm:creditdown")],
        [("✏️ تغییر متن‌ها", "adm:texts")],
        [("📊 گزارش کامل", "adm:report"), ("📣 اعلان همگانی", "adm:announce")],
        [("🤖 بات‌های متصل", "adm:bots"), ("🧾 لاگ مدیریت", "adm:logs")],
        [("⚙️ تنظیمات", "adm:settings")],
        [("⬅️ منوی اصلی", "adm:main")],
    ]
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows])


def _reset_admin_state(B, uid):
    st = B.S.setdefault(uid, {})
    st.update({"mode":"main", "admin":True, "admin_plus_mode":None, "night_mode":None})
    return st


async def _send_menu(message):
    await message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=menu())


async def _entry(update, context, B):
    msg = getattr(update, "effective_message", None); user = getattr(update, "effective_user", None)
    if not msg or not user or not _admin(B, user.id): return
    if (getattr(msg, "text", "") or "").strip() not in ADMIN_TEXTS: return
    _reset_admin_state(B, user.id); await _send_menu(msg); raise ApplicationHandlerStop


async def _add_partner_callback(update, context, B):
    q = update.callback_query
    if not q or q.data != "adm:addpartner": return
    if not _admin(B, q.from_user.id):
        await q.answer("❌ دسترسی مدیریت ندارید.", show_alert=True); raise ApplicationHandlerStop
    st = _reset_admin_state(B, q.from_user.id)
    st["canonical_add_partner"] = "name"
    await q.answer(); await q.message.reply_text("➕ افزودن همکار\n\n👤 نام و نام خانوادگی همکار را وارد کنید:")
    raise ApplicationHandlerStop


async def _night_callback(update, context, B):
    try:
        import telegram_admin_cleanup_and_night_switch_v1 as N
        result = N._callback(update, context, B)
        if inspect.isawaitable(result): await result
    except Exception:
        try: await update.callback_query.message.reply_text("❌ کنترل شب انجام نشد. دوباره تلاش کنید.", reply_markup=menu())
        except Exception: pass
    raise ApplicationHandlerStop


async def _callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q or not _admin(B, q.from_user.id): return
    data = str(q.data or "")
    if data == "adm:addpartner": return await _add_partner_callback(update, context, B)
    if data in {"adm:night_on", "adm:night_off"}:
        return await _night_callback(update, context, B)
    if not data.startswith("adm:"): return
    try: await q.answer()
    except Exception: pass
    try:
        import telegram_admin_plus as A
        result = A._callback(update, context, B)
        if inspect.isawaitable(result): await result
    except Exception:
        try: await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد.\n\nاز منوی مدیریت دوباره انتخاب کنید.", reply_markup=menu())
        except Exception: pass
    raise ApplicationHandlerStop


async def _text(update, context, B):
    msg = getattr(update, "effective_message", None); user = getattr(update, "effective_user", None)
    if not msg or not user or not _admin(B, user.id): return
    t = (getattr(msg, "text", "") or "").strip()
    if t in ADMIN_TEXTS:
        _reset_admin_state(B, user.id); await _send_menu(msg); raise ApplicationHandlerStop
    st = B.S.setdefault(user.id, {})
    if st.get("canonical_add_partner"):
        mode = st["canonical_add_partner"]
        if t in {"❌ انصراف", "لغو", "انصراف"}:
            st.pop("canonical_add_partner", None); await msg.reply_text("❌ عملیات لغو شد.", reply_markup=menu()); raise ApplicationHandlerStop
        if mode == "name":
            if len(t) < 2: await msg.reply_text("❌ نام معتبر وارد کنید."); raise ApplicationHandlerStop
            st["canonical_partner_name"] = t; st["canonical_add_partner"] = "phone"
            await msg.reply_text("📱 شماره موبایل همکار را وارد کنید:"); raise ApplicationHandlerStop
        if mode == "phone":
            phone = re.sub(r"\D", "", t).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
            if phone.startswith("98"): phone = "0" + phone[2:]
            if not re.fullmatch(r"09\d{9}", phone): await msg.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود."); raise ApplicationHandlerStop
            if B.db.conn.execute("SELECT 1 FROM partners WHERE phone=?", (phone,)).fetchone(): await msg.reply_text("❌ این شماره قبلاً به عنوان همکار ثبت شده است."); raise ApplicationHandlerStop
            st["canonical_partner_phone"] = phone; st["canonical_add_partner"] = "password"
            await msg.reply_text("🔐 رمز ورود همکار را وارد کنید (حداقل ۴ کاراکتر):"); raise ApplicationHandlerStop
        if mode == "password":
            if len(t) < 4: await msg.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد."); raise ApplicationHandlerStop
            from core import hash_password
            now = B.now()
            B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (st["canonical_partner_phone"], hash_password(t), st["canonical_partner_name"], 1, 0, now, now))
            B.db.conn.commit(); phone = st["canonical_partner_phone"]; name = st["canonical_partner_name"]
            row = B.db.conn.execute("SELECT id FROM partners WHERE phone=?", (phone,)).fetchone()
            for k in ("canonical_add_partner","canonical_partner_name","canonical_partner_phone"): st.pop(k, None)
            await msg.reply_text(f"✅ همکار با موفقیت اضافه شد.\n\n👤 {name}\n📱 {phone}\n🆔 شناسه: {row['id'] if row else '-'}\n💰 موجودی اولیه: 0 تومان", reply_markup=menu()); raise ApplicationHandlerStop

    # Delegate active admin-plus text modes, but do not consume ordinary admin/customer text.
    if st.get("admin_plus_mode"):
        try:
            import telegram_admin_plus as A
            result = A._text(update, context, B)
            if inspect.isawaitable(result): await result
        except Exception:
            await msg.reply_text("❌ ورود اطلاعات با خطا مواجه شد. دوباره تلاش کنید.", reply_markup=menu())
        raise ApplicationHandlerStop


def install(app, B):
    B.amenu = menu; B.admin_menu_final = menu
    try:
        import telegram_admin_plus as A; A._admin_menu = menu
    except Exception: pass
    if getattr(B, "_canonical_admin_final_v5", False): return True
    app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B), pattern=r"^adm:"), group=-100000001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c:_text(u,c,B)), group=-100000000)
    B._canonical_admin_final_v5 = True
    return True
