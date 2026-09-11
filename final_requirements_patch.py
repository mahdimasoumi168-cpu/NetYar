"""Final user-facing requirements layer.

Kept isolated from legacy handlers. Idempotent and intentionally defensive so
existing Telegram/Rubika flows keep working while the requested UX fixes are
applied consistently.
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
    # Fast path through the canonical helper.
    try:
        row = db.partner(phone)
        if row:
            return row
    except Exception:
        pass
    # Compatibility path for older rows saved as +98/0098/Arabic digits.
    try:
        rows = db.conn.execute("SELECT * FROM partners WHERE active=1").fetchall()
        for row in rows:
            stored = _norm_phone(row["phone"])
            if stored == phone:
                return row
    except Exception:
        log.exception("partner compatibility lookup failed")
    return None


def install():
    import bot as B

    if getattr(B, "_final_requirements_installed", False):
        return

    # ------------------------------------------------------------------
    # 1) Stable cancel: never retain an old flow mode or stale service data.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 2) Partner login: one canonical phone format for Telegram and old DBs.
    # ------------------------------------------------------------------
    old_ptext = B.ptext

    async def stable_ptext(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (getattr(update.message, "text", "") or "").strip()
        if st.get("mode") == "p_phone":
            phone = _norm_phone(text)
            partner = _find_partner(B.db, phone)
            if not partner:
                return await update.message.reply_text(
                    "❌ همکار با این شماره پیدا نشد.\n📱 شماره را به صورت 09xxxxxxxxx وارد کنید.",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st.update({"phone": phone, "mode": "p_pass"})
            return await update.message.reply_text("🔐 رمز عبور همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        return await old_ptext(update, context)

    B.ptext = stable_ptext

    # ------------------------------------------------------------------
    # 3) Iranian menu: only tracking / partner / cancel.
    # ------------------------------------------------------------------
    old_status = B.statuscb

    async def stable_status(update, context):
        q = update.callback_query
        if q.data != "st:iranian":
            return await old_status(update, context)
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        st["status"] = "iranian"
        st.pop("mode", None)
        st.pop("editing_request_id", None)
        return await q.message.reply_text(
            "🇮🇷 منوی خدمات ایرانی\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=B.kb([["🎫 پیگیری", "🔵 👥 پنل همکاران"], [B.CANCEL]]),
        )

    B.statuscb = stable_status

    # ------------------------------------------------------------------
    # 4) Residence booklet: same government flow as passport, but replace
    #    passport number with booklet number.
    # ------------------------------------------------------------------
    old_gov = B.gov

    async def stable_gov(update, context):
        uid = update.effective_user.id
        old = dict(B.S.get(uid, {}))
        B.S[uid] = {
            "mode": "gov_doc_type",
            "lang": old.get("lang", "fa"),
            "gov_files": {},
            "partner_id": old.get("partner_id"),
        }
        return await update.message.reply_text(
            "🪪 نوع مدرک مشترک را انتخاب کنید:",
            reply_markup=B.kb([["🪪 کارت آمایش", "🛂 گذرنامه"], ["📗 دفترچه اقامت"], [B.CANCEL]]),
        )

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
                return await update.message.reply_text("❌ شماره دفترچه اقامت را صحیح وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
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

    # ------------------------------------------------------------------
    # 5) Real partner panel: stable, understandable options.
    # ------------------------------------------------------------------
    def partner_panel(uid):
        lang = B.S.get(uid, {}).get("lang", "fa")
        return B.kb([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🎫 درخواست‌های من", "🔎 پیگیری کد"],
            ["📋 سوابق", "💰 موجودی"],
            ["✉️ ارسال تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            [B.CANCEL],
        ])

    B.partner_kb = partner_panel

    # ------------------------------------------------------------------
    # 6) Make every currently undefined partner button safe instead of
    #    silently falling out of the router.
    # ------------------------------------------------------------------
    old_router = B.router

    async def stable_router(update, context):
        uid = update.effective_user.id
        text = (getattr(update.message, "text", "") or "").strip()
        st = B.S.setdefault(uid, {})
        if text == "✉️ ارسال تیکت به مدیریت":
            if not st.get("partner_id"):
                return await update.message.reply_text("❌ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
            st["mode"] = "partner_ticket_text"
            return await update.message.reply_text("✉️ متن تیکت خود را بنویسید:\n\nمثلاً مشکل، درخواست یا توضیح خود را کامل ارسال کنید.", reply_markup=B.kb([[B.CANCEL]]))
        if st.get("mode") == "partner_ticket_text":
            if text == B.CANCEL:
                return await B.cancel(update, context)
            message = (
                "✉️ تیکت جدید همکار\n\n"
                f"👤 شناسه همکار: {st.get('partner_id')}\n"
                f"📱 شماره: {st.get('phone', '-') }\n\n"
                f"📝 متن تیکت:\n{text}"
            )
            try:
                await B.notify_admins(context.application, message)
            except Exception:
                log.exception("partner ticket notification failed")
                return await update.message.reply_text("❌ ارسال تیکت ناموفق بود. دوباره تلاش کنید.", reply_markup=partner_panel(uid))
            st["mode"] = None
            return await update.message.reply_text("✅ تیکت شما برای مدیریت ارسال شد.", reply_markup=partner_panel(uid))
        if text in {"🎫 درخواست‌های من", "🎫 درخواست ها"} and st.get("partner_id"):
            rows = B.db.conn.execute(
                "SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20",
                (st["partner_id"],),
            ).fetchall()
            body = "\n".join(f"🎫 {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount'] or 0):,} تومان" for r in rows) or "هنوز درخواستی ثبت نشده است."
            return await update.message.reply_text("📋 درخواست‌های من\n\n" + body, reply_markup=partner_panel(uid))
        return await old_router(update, context)

    B.router = stable_router

    # ------------------------------------------------------------------
    # 7) Admin panel additions: Iranian/foreign service groups and readable
    #    text-management entry point. Existing admin handlers remain intact.
    # ------------------------------------------------------------------
    old_amenu = B.amenu

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
