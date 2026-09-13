"""Final Telegram admin/navigation hardening layer.

Owns the few high-conflict admin actions that historically were intercepted by
legacy handlers: complete admin logout, partner creation, sequential per-partner
pricing, and the canonical text-editor entry.  It deliberately runs before
legacy admin callbacks and keeps all existing service handlers intact.
"""
from __future__ import annotations
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop


def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(str(t), callback_data=str(d)) for t, d in row] for row in rows])


def _admin_menu(A):
    return A._admin_menu()


def _norm_phone(v):
    s = str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"\D", "", s)
    if s.startswith("0098"): s = "0" + s[4:]
    elif s.startswith("98"): s = "0" + s[2:]
    if len(s) == 10 and s.startswith("9"): s = "0" + s
    return s


def _services(B):
    return B.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall()


def _set_mode(st, mode):
    st["admin_final_mode"] = mode
    st["admin_plus_mode"] = None


async def install(app, B):
    import telegram_admin_plus as A
    old_menu = A._admin_menu

    if not getattr(A, "_final_admin_nav_v3", False):
        def menu():
            base = old_menu()
            rows = [list(r) for r in base.inline_keyboard]
            labels = {str(b.text) for row in rows for b in row}
            # Put management additions before the main-menu row.
            additions = []
            if "➕ افزودن همکار جدید" not in labels:
                additions.append([InlineKeyboardButton("➕ افزودن همکار جدید", callback_data="adm:add_partner")])
            if "📋 قیمت‌گذاری تک‌تک همکار" not in labels:
                additions.append([InlineKeyboardButton("📋 قیمت‌گذاری تک‌تک همکار", callback_data="adm:partner_prices_seq")])
            if "📝 ویرایش کامل متن‌ها" not in labels:
                additions.append([InlineKeyboardButton("📝 ویرایش کامل متن‌ها", callback_data="adm:ui_texts")])
            if "🚪 خروج کامل از مدیریت" not in labels:
                additions.append([InlineKeyboardButton("🚪 خروج کامل از مدیریت", callback_data="adm:full_logout")])
            insert_at = max(0, len(rows) - 1)
            rows[insert_at:insert_at] = additions
            return InlineKeyboardMarkup(rows)
        A._admin_menu = menu
        A._final_admin_nav_v3 = True

    async def callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = str(q.data or "")
        if data not in {"adm:add_partner", "adm:partner_prices_seq", "adm:full_logout", "adm:ui_texts"}:
            return
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})

        if data == "adm:full_logout":
            # Hard reset every privileged/partner flow key. Keep only language
            # and identity-safe presentation state so the next click is public.
            lang = st.get("lang", "fa")
            for k in list(st):
                if k != "lang":
                    st.pop(k, None)
            st.update({"lang": lang, "mode": None, "partner_logged_out": True,
                       "partner_active": False, "partner_id": None})
            return await q.message.reply_text("🚪 خروج کامل از پنل مدیریت انجام شد.\n\nبه منوی مشترکین برگشتید.", reply_markup=B.main(uid))

        if data == "adm:ui_texts":
            # Delegate to the comprehensive catalog editor; this is the single
            # canonical editor already present in the repository.
            try:
                import admin_editable_texts as E
                return await q.message.reply_text("📝 ویرایش کامل متن‌های ربات\n\nاز فهرست زیر متن موردنظر را انتخاب کنید. متن‌ها از تمام ماژول‌های فعال ربات جمع‌آوری می‌شوند.", reply_markup=E._kb(E._page(B, 0)))
            except Exception:
                return await q.message.reply_text("❌ ویرایشگر متن فعلاً آماده نیست. دوباره تلاش کنید.", reply_markup=_admin_menu(A))

        if data == "adm:add_partner":
            _set_mode(st, "add_partner_name")
            return await q.message.reply_text("➕ افزودن همکار جدید\n\n👤 نام همکار را وارد کنید:", reply_markup=_kb([[('❌ انصراف','adm:menu')]]))

        if data == "adm:partner_prices_seq":
            _set_mode(st, "ppseq_partner")
            return await q.message.reply_text("📋 قیمت‌گذاری تک‌تک خدمات همکار\n\n👤 شناسه، شماره موبایل یا نام همکار را وارد کنید:")

    async def text(update, context):
        if not update.message or not B.admin(update.effective_user.id):
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("admin_final_mode")
        if not mode:
            return
        t = (update.message.text or "").strip()
        if t in {"❌ انصراف", "لغو", "انصراف"}:
            st["admin_final_mode"] = None
            return await update.message.reply_text("لغو شد.", reply_markup=_admin_menu(A))

        if mode == "add_partner_name":
            if len(t) < 2 or len(t) > 100:
                return await update.message.reply_text("❌ نام همکار معتبر نیست. دوباره وارد کنید:")
            st["new_partner_name"] = t
            _set_mode(st, "add_partner_phone")
            return await update.message.reply_text("📱 شماره موبایل اختصاصی همکار را وارد کنید:")

        if mode == "add_partner_phone":
            phone = _norm_phone(t)
            if not re.fullmatch(r"09\d{9}", phone):
                return await update.message.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789")
            if B.db.conn.execute("SELECT 1 FROM partners WHERE phone=?", (phone,)).fetchone():
                return await update.message.reply_text("❌ این شماره قبلاً برای یک همکار ثبت شده است.")
            st["new_partner_phone"] = phone
            _set_mode(st, "add_partner_password")
            return await update.message.reply_text("🔐 رمز ورود همکار را وارد کنید (حداقل ۴ کاراکتر):")

        if mode == "add_partner_password":
            if len(t) < 4:
                return await update.message.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.")
            try:
                from core import hash_password
                ph = hash_password(t)
            except Exception:
                return await update.message.reply_text("❌ امکان ساخت رمز وجود ندارد. لطفاً دوباره تلاش کنید.")
            B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (st["new_partner_phone"], ph, st["new_partner_name"], 1, 0, B.now(), B.now()))
            B.db.conn.commit()
            name, phone = st["new_partner_name"], st["new_partner_phone"]
            for k in list(st):
                if k.startswith("new_partner_"):
                    st.pop(k, None)
            st["admin_final_mode"] = None
            return await update.message.reply_text(f"✅ همکار جدید با موفقیت اضافه شد.\n\n👤 نام: {name}\n📱 موبایل: {phone}\n💰 اعتبار اولیه: 0 تومان", reply_markup=_admin_menu(A))

        if mode == "ppseq_partner":
            v = t
            if v.isdigit():
                p = B.db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=? LIMIT 1", (int(v), v)).fetchone()
            else:
                p = B.db.conn.execute("SELECT * FROM partners WHERE phone=? OR name LIKE ? ORDER BY id LIMIT 1", (v, f"%{v}%")).fetchone()
            if not p:
                return await update.message.reply_text("❌ همکار پیدا نشد. شناسه، شماره یا نام را صحیح وارد کنید:")
            services = [r for r in _services(B) if int(r["active"] or 0)]
            if not services:
                return await update.message.reply_text("❌ هیچ خدمت فعالی برای قیمت‌گذاری وجود ندارد.", reply_markup=_admin_menu(A))
            st.update({"ppseq_partner_id": int(p["id"]), "ppseq_index": 0, "ppseq_services": [str(r["key"]) for r in services], "ppseq_values": {}, "ppseq_names": {str(r["key"]): str(r["name"]) for r in services}})
            _set_mode(st, "ppseq_price")
            r = services[0]
            cur = B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?", (int(p["id"]), str(r["key"]))).fetchone()
            current = int(cur["price"]) if cur else int(r["price"] or 0)
            return await update.message.reply_text(f"👤 همکار: {p['name'] or '-'}\n📱 {p['phone']}\n\n🔹 خدمت ۱ از {len(services)}: {r['name']}\n💰 قیمت فعلی: {current:,} تومان\n\nقیمت جدید همین خدمت را فقط به تومان وارد کنید:")

        if mode == "ppseq_price":
            raw = t.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
            raw = re.sub(r"[,٬\s]", "", raw)
            if not raw.isdigit():
                return await update.message.reply_text("❌ فقط مبلغ را به عدد وارد کنید. مثال: 420000")
            amount = int(raw)
            if amount < 0:
                return await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
            idx = int(st.get("ppseq_index", 0))
            keys = st.get("ppseq_services", [])
            if idx >= len(keys):
                st["admin_final_mode"] = None
                return await update.message.reply_text("⚠️ این مرحله قبلاً تمام شده است.", reply_markup=_admin_menu(A))
            key = keys[idx]
            st.setdefault("ppseq_values", {})[key] = amount
            idx += 1
            st["ppseq_index"] = idx
            if idx < len(keys):
                next_key = keys[idx]
                r = B.db.conn.execute("SELECT name,price FROM services WHERE key=?", (next_key,)).fetchone()
                cur = B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?", (int(st["ppseq_partner_id"]), next_key)).fetchone()
                current = int(cur["price"]) if cur else int(r["price"] or 0)
                return await update.message.reply_text(f"✅ قیمت «{st['ppseq_names'][key]}» دریافت شد: {amount:,} تومان\n\n🔹 خدمت {idx+1} از {len(keys)}: {r['name']}\n💰 قیمت فعلی: {current:,} تومان\n\nقیمت جدید این خدمت را وارد کنید:")
            for k, val in st["ppseq_values"].items():
                B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices(partner_id,service_key,price,updated_at) VALUES(?,?,?,?)", (int(st["ppseq_partner_id"]), k, int(val), B.now()))
            B.db.conn.commit()
            pid = int(st["ppseq_partner_id"])
            p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
            count = len(st["ppseq_values"])
            st["admin_final_mode"] = None
            st.pop("ppseq_values", None); st.pop("ppseq_services", None); st.pop("ppseq_names", None); st.pop("ppseq_index", None); st.pop("ppseq_partner_id", None)
            return await update.message.reply_text(f"✅ قیمت‌گذاری تک‌تک کامل شد.\n\n👤 همکار: {p['name'] if p else '-'}\n📱 {p['phone'] if p else '-'}\n🔢 تعداد خدمات ثبت‌شده: {count}", reply_markup=_admin_menu(A))

    # Must run before the legacy admin routers.
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^adm:(add_partner|partner_prices_seq|full_logout|ui_texts)$"), group=-20000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-19999)
    B._final_admin_nav_v3_installed = True
    return True
