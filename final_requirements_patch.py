"""Final user-facing requirements layer.

Kept isolated from legacy handlers. Idempotent and defensive so existing
Telegram/Rubika flows keep working while the requested UX fixes are applied.
"""
import logging
import re

log = logging.getLogger("netyar.final_requirements")


def _norm_phone(v):
    s = str(v or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s if re.fullmatch(r"09\d{9}", s) else None


def _find_partner(db, value):
    phone = _norm_phone(value)
    if not phone:
        return None
    try:
        row = db.partner(phone)
        if row:
            return row
    except Exception:
        pass
    try:
        rows = db.conn.execute("SELECT * FROM partners WHERE active=1").fetchall()
        for row in rows:
            if _norm_phone(row["phone"]) == phone:
                return row
    except Exception:
        log.exception("partner compatibility lookup failed")
    return None


def install():
    import bot as B
    if getattr(B, "_final_requirements_installed", False):
        return

    old_cancel = B.cancel
    async def stable_cancel(update, context):
        uid = update.effective_user.id
        old = dict(B.S.get(uid, {}))
        lang = old.get("lang", "fa")
        partner_id = old.get("partner_id")
        partner_active = old.get("partner_active", True)
        B.S[uid] = {"lang": lang}
        if partner_id:
            B.S[uid].update({"partner_id": partner_id, "partner_active": partner_active})
        return await update.message.reply_text(
            "❌ عملیات لغو شد.",
            reply_markup=B.partner_kb(lang) if partner_id and partner_active else B.main(uid),
        )
    B.cancel = stable_cancel

    old_ptext = B.ptext
    async def stable_ptext(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (getattr(update.message, "text", "") or "").strip()
        if st.get("mode") == "p_phone":
            phone = _norm_phone(text)
            partner = _find_partner(B.db, phone)
            if not partner:
                return await update.message.reply_text("❌ همکار با این شماره پیدا نشد.\n📱 شماره را به صورت 09xxxxxxxxx وارد کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            st.update({"phone": phone, "mode": "p_pass"})
            return await update.message.reply_text("🔐 رمز عبور همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        return await old_ptext(update, context)
    B.ptext = stable_ptext

    old_status = B.statuscb
    async def stable_status(update, context):
        q = update.callback_query
        if q.data != "st:iranian":
            return await old_status(update, context)
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        st.update({"status": "iranian"})
        st.pop("mode", None)
        return await q.message.reply_text("🇮🇷 منوی خدمات ایرانی\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=B.kb([["🎫 پیگیری", "🔵 👥 پنل همکاران"], [B.CANCEL]]))
    B.statuscb = stable_status

    old_gov = B.gov
    async def stable_gov(update, context):
        uid = update.effective_user.id
        old = dict(B.S.get(uid, {}))
        B.S[uid] = {"mode": "gov_doc_type", "lang": old.get("lang", "fa"), "gov_files": {}, "partner_id": old.get("partner_id")}
        return await update.message.reply_text("🪪 نوع مدرک مشترک را انتخاب کنید:", reply_markup=B.kb([["🪪 کارت آمایش", "🛂 گذرنامه"], ["📗 دفترچه اقامت"], [B.CANCEL]]))
    B.gov = stable_gov

    old_service_text = B.service_text
    async def stable_service_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (getattr(update.message, "text", "") or "").strip()
        if st.get("mode") == "gov_doc_type" and text == "📗 دفترچه اقامت":
            st["gov_doc_type"] = "residence_booklet"
            st["mode"] = "gov_phone"
            return await update.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if st.get("mode") == "gov_special" and st.get("gov_doc_type") == "residence_booklet":
            if len(text) < 3:
                return await update.message.reply_text("❌ اطلاعات دفترچه اقامت را صحیح وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            st["gov_special"] = text
            st["mode"] = "gov_booklet_number"
            return await update.message.reply_text("📗 شماره دفترچه اقامت را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if st.get("mode") == "gov_booklet_number":
            if len(text) < 3:
                return await update.message.reply_text("❌ شماره دفترچه اقامت را صحیح وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            st["gov_booklet_number"] = text
            st["mode"] = "gov_photo"
            return await update.message.reply_text("📸 تصویر دفترچه اقامت را ارسال کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        return await old_service_text(update, context)
    B.service_text = stable_service_text

    def partner_panel(uid):
        return B.kb([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🎫 درخواست‌های من", "🔎 پیگیری کد"],
            ["📋 سوابق", "💰 موجودی"],
            ["✉️ ارسال تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            [B.CANCEL],
        ])
    B.partner_kb = partner_panel

    def admin_service_rows():
        rows = []
        try:
            for r in B.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall():
                rows.append([f"{'🟢' if int(r['active'] or 0) else '🔴'} {r['name']}"])
        except Exception:
            pass
        return rows or [["⏳ هنوز خدمتی تعریف نشده است."]]

    old_router = B.router
    async def stable_router(update, context):
        uid = update.effective_user.id
        text = (getattr(update.message, "text", "") or "").strip()
        st = B.S.setdefault(uid, {})

        # Partner ticket must collect free text before notifying admins.
        if text == "✉️ ارسال تیکت به مدیریت":
            if not st.get("partner_id"):
                return await update.message.reply_text("❌ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
            st["mode"] = "partner_ticket_text"
            return await update.message.reply_text("✉️ متن تیکت خود را بنویسید:\n\nمشکل یا درخواست خود را کامل ارسال کنید.", reply_markup=B.kb([[B.CANCEL]]))
        if st.get("mode") == "partner_ticket_text":
            if text == B.CANCEL:
                return await B.cancel(update, context)
            message = f"✉️ تیکت جدید همکار\n\n👤 شناسه همکار: {st.get('partner_id')}\n📱 شماره: {st.get('phone', '-')}\n\n📝 متن تیکت:\n{text}"
            try:
                await B.notify_admins(context.application, message)
            except Exception:
                log.exception("partner ticket notification failed")
                return await update.message.reply_text("❌ ارسال تیکت ناموفق بود.", reply_markup=partner_panel(uid))
            st["mode"] = None
            return await update.message.reply_text("✅ تیکت شما برای مدیریت ارسال شد.", reply_markup=partner_panel(uid))

        if text in {"🎫 درخواست‌های من", "🎫 درخواست ها"} and st.get("partner_id"):
            rows = B.db.conn.execute("SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20", (st["partner_id"],)).fetchall()
            body = "\n".join(f"🎫 {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount'] or 0):,} تومان" for r in rows) or "هنوز درخواستی ثبت نشده است."
            return await update.message.reply_text("📋 درخواست‌های من\n\n" + body, reply_markup=partner_panel(uid))

        # Readable admin service management: two explicit groups.
        if B.admin(uid) and text in {"🛠 باز/بسته خدمات", "🔧 مدیریت خدمات"}:
            st["final_admin_mode"] = "services"
            return await update.message.reply_text("🔧 باز و بسته کردن خدمات\n\n🇮🇷 خدمات ایرانی\n🇦🇫 خدمات اتباع\n\n🟢 باز = فعال | 🔴 بسته = غیرفعال\nروی خدمت موردنظر بزنید:", reply_markup=B.kb(admin_service_rows() + [["🇮🇷 مدیریت خدمات ایرانی"], ["🇦🇫 مدیریت خدمات اتباع"], ["⬅️ منوی مدیریت"]]))
        if B.admin(uid) and st.get("final_admin_mode") == "services":
            if text == "⬅️ منوی مدیریت":
                st["final_admin_mode"] = None
                return await update.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            if text in {"🇮🇷 مدیریت خدمات ایرانی", "🇦🇫 مدیریت خدمات اتباع"}:
                st["final_admin_category"] = "iranian" if text.startswith("🇮🇷") else "foreign"
                return await update.message.reply_text("📂 این بخش آماده مدیریت خدمات همان دسته است.\nبرای تغییر وضعیت، خدمت را از فهرست بالا انتخاب کنید.", reply_markup=B.kb(admin_service_rows() + [["⬅️ منوی مدیریت"]]))
            try:
                rows = B.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall()
                row = next((r for r in rows if str(r["name"]) in text), None)
                if row:
                    st["service_key"] = row["key"]
                    st["final_admin_mode"] = "service_action"
                    return await update.message.reply_text(f"🔧 {row['name']}\n📌 وضعیت: {'باز' if row['active'] else 'بسته'}\n💰 قیمت: {int(row['price'] or 0):,} تومان", reply_markup=B.kb([["🔄 باز/بسته"], ["✏️ تغییر نام"], ["💰 تغییر قیمت"], ["⬅️ بازگشت"]]))
            except Exception:
                pass
        if B.admin(uid) and st.get("final_admin_mode") == "service_action":
            key = st.get("service_key")
            if text in {"⬅️ بازگشت", "⬅️ منوی مدیریت"}:
                st["final_admin_mode"] = "services"
                return await update.message.reply_text("🔧 باز و بسته کردن خدمات", reply_markup=B.kb(admin_service_rows() + [["⬅️ منوی مدیریت"]]))
            if key and text == "🔄 باز/بسته":
                r = B.db.conn.execute("SELECT active FROM services WHERE key=?", (key,)).fetchone()
                if r:
                    new = 0 if int(r["active"] or 0) else 1
                    B.db.conn.execute("UPDATE services SET active=? WHERE key=?", (new, key)); B.db.conn.commit()
                    return await update.message.reply_text("🟢 خدمت باز شد." if new else "🔴 خدمت بسته شد.", reply_markup=B.kb(admin_service_rows() + [["⬅️ منوی مدیریت"]]))
            if key and text == "✏️ تغییر نام":
                st["final_admin_mode"] = "service_name"
                return await update.message.reply_text("✏️ نام جدید خدمت را ارسال کنید:", reply_markup=B.kb([["⬅️ بازگشت"]]))
            if key and text == "💰 تغییر قیمت":
                st["final_admin_mode"] = "service_price"
                return await update.message.reply_text("💰 قیمت جدید را فقط به تومان وارد کنید:", reply_markup=B.kb([["⬅️ بازگشت"]]))
        if B.admin(uid) and st.get("final_admin_mode") == "service_name":
            if text == "⬅️ بازگشت":
                st["final_admin_mode"] = "service_action"
                return await update.message.reply_text("🔧 گزینه خدمت را انتخاب کنید:", reply_markup=B.kb([["🔄 باز/بسته"], ["✏️ تغییر نام"], ["💰 تغییر قیمت"], ["⬅️ بازگشت"]]))
            key = st.get("service_key")
            if key:
                B.db.conn.execute("UPDATE services SET name=? WHERE key=?", (text, key)); B.db.conn.commit()
                st["final_admin_mode"] = "services"
                return await update.message.reply_text("✅ نام خدمت ذخیره شد.", reply_markup=B.kb(admin_service_rows() + [["⬅️ منوی مدیریت"]]))
        if B.admin(uid) and st.get("final_admin_mode") == "service_price":
            if text == "⬅️ بازگشت":
                st["final_admin_mode"] = "service_action"
                return await update.message.reply_text("🔧 گزینه خدمت را انتخاب کنید:", reply_markup=B.kb([["🔄 باز/بسته"], ["✏️ تغییر نام"], ["💰 تغییر قیمت"], ["⬅️ بازگشت"]]))
            raw = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace(",", "").replace("٬", "").replace(" ", "").replace("تومان", "")
            if not raw.isdigit():
                return await update.message.reply_text("❌ قیمت باید عدد باشد.")
            key = st.get("service_key")
            amount = int(raw)
            B.db.conn.execute("UPDATE services SET price=? WHERE key=?", (amount, key)); B.db.set_setting("price_" + key, amount); B.db.conn.commit()
            st["final_admin_mode"] = "services"
            return await update.message.reply_text(f"✅ قیمت به {amount:,} تومان تغییر کرد.", reply_markup=B.kb(admin_service_rows() + [["⬅️ منوی مدیریت"]]))

        if B.admin(uid) and text == "📝 مدیریت متن‌ها":
            st["final_admin_mode"] = "text_menu"
            return await update.message.reply_text("📝 مدیریت متن‌ها\n\nهر مورد را انتخاب کنید؛ سپس متن جدید را ارسال کنید:", reply_markup=B.kb([["👋 خوش‌آمدگویی"], ["🪪 متن خدمات اتباع"], ["🇮🇷 متن خدمات ایرانی"], ["📞 متن پشتیبانی"], ["❌ متن خطاها"], ["⬅️ منوی مدیریت"]]))
        if B.admin(uid) and st.get("final_admin_mode") == "text_menu":
            if text == "⬅️ منوی مدیریت":
                st["final_admin_mode"] = None
                return await update.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            key = {"👋 خوش‌آمدگویی":"admin_text_welcome", "🪪 متن خدمات اتباع":"admin_text_foreign", "🇮🇷 متن خدمات ایرانی":"admin_text_iranian", "📞 متن پشتیبانی":"admin_text_support", "❌ متن خطاها":"admin_text_error"}.get(text)
            if key:
                st["final_text_key"] = key; st["final_admin_mode"] = "text_edit"
                current = B.db.setting(key, "(هنوز متنی ذخیره نشده است)")
                return await update.message.reply_text(f"✏️ ویرایش متن\n\nمتن فعلی:\n{current}\n\nمتن جدید را همینجا ارسال کنید:", reply_markup=B.kb([["⬅️ بازگشت"]]))
        if B.admin(uid) and st.get("final_admin_mode") == "text_edit":
            if text == "⬅️ بازگشت":
                st["final_admin_mode"] = "text_menu"
                return await update.message.reply_text("📝 مدیریت متن‌ها", reply_markup=B.kb([["👋 خوش‌آمدگویی"], ["🪪 متن خدمات اتباع"], ["🇮🇷 متن خدمات ایرانی"], ["📞 متن پشتیبانی"], ["❌ متن خطاها"], ["⬅️ منوی مدیریت"]]))
            B.db.set_setting(st.get("final_text_key"), text)
            st["final_admin_mode"] = "text_menu"
            return await update.message.reply_text("✅ متن ذخیره شد و از این به بعد مقدار ذخیره‌شده قابل استفاده است.", reply_markup=B.kb([["👋 خوش‌آمدگویی"], ["🪪 متن خدمات اتباع"], ["🇮🇷 متن خدمات ایرانی"], ["📞 متن پشتیبانی"], ["❌ متن خطاها"], ["⬅️ منوی مدیریت"]]))

        if B.admin(uid) and text in {"💰 مدیریت قیمت‌ها", "📋 مدیریت درخواست‌ها", "✉️ مدیریت تیکت‌ها", "📎 فایل‌ها و مدارک", "👑 مدیریت مدیران", "📊 گزارش‌ها"}:
            return await update.message.reply_text("⏳ این بخش فعلاً بسته است و هنوز فعال نشده است.", reply_markup=B.amenu())

        return await old_router(update, context)

    B.router = stable_router

    def full_admin_menu():
        return B.kb([
            ["👥 مدیریت همکاران", "👤 مدیریت کاربران"],
            ["🛠 باز/بسته خدمات", "📝 مدیریت متن‌ها"],
            ["💰 مدیریت قیمت‌ها", "📋 مدیریت درخواست‌ها"],
            ["✉️ مدیریت تیکت‌ها", "📎 فایل‌ها و مدارک"],
            ["👑 مدیریت مدیران", "📊 گزارش‌ها"],
            ["🤖 بات‌های متصل", "➕ افزودن بات"],
            ["⬅️ منوی اصلی"],
        ])
    B.amenu = full_admin_menu
    B._final_requirements_installed = True
    log.info("final requirements patch installed")
