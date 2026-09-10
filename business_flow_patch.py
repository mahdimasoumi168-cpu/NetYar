"""Safe business-flow fixes layered on top of the existing runtime.

This module intentionally wraps the already-working router instead of replacing
core handlers. It fixes the remaining UI/payment/account flows without touching
Rubika/Telegram transport code.
"""
import logging
import re

log = logging.getLogger("netyar.business_flow_patch")


def _amount(text):
    s = str(text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = s.replace(",", "").replace("٬", "").replace("تومان", "").replace(" ", "")
    return int(s) if s.isdigit() and int(s) > 0 else None


def install():
    import bot as B
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if getattr(B, "_business_flow_patch_installed", False):
        return

    old_main = B.main
    def main(uid):
        markup = old_main(uid)
        st = B.S.get(uid, {})
        if st.get("status") != "iranian":
            return markup
        return B.kb([
            ["🎫 پیگیری", "👥 پنل همکاران"],
            ["💰 اعتبار من", "⬅️ بازگشت"],
            ["📞 تماس با ما", "📝 ثبت شکایت مشتریان"],
            [B.CANCEL],
        ])
    B.main = main

    # Amount -> receipt. The receipt handler below creates the single topup row.
    old_service_text = B.service_text
    async def service_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        t = (update.message.text or "").strip()
        if st.get("mode") == "topup_amount":
            amount = _amount(t)
            if not amount:
                return await update.message.reply_text("❌ مبلغ نامعتبر است. فقط عدد وارد کنید؛ مثال: 500000", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            pid = st.get("partner_id")
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
            if not p:
                st["mode"] = None
                return await update.message.reply_text("❌ حساب همکار پیدا نشد.", reply_markup=B.main(uid))
            st["topup_amount"] = amount
            st["mode"] = "topup_receipt"
            return await update.message.reply_text(
                f"💰 مبلغ شارژ: {amount:,} تومان\n\n📎 حالا تصویر یا فایل رسید واریز را ارسال کنید.\n\nبعد از ارسال رسید، درخواست برای مدیریت فرستاده می‌شود.",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        return await old_service_text(update, context)
    B.service_text = service_text

    # Receipt must reach management as an actual Telegram photo/document.
    old_media = B.media
    async def media(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") == "topup_receipt":
            fid = update.message.photo[-1].file_id if update.message.photo else (update.message.document.file_id if update.message.document else "")
            if not fid:
                return await update.message.reply_text("❌ لطفاً تصویر یا فایل رسید را ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            pid = st.get("partner_id")
            amount = int(st.get("topup_amount") or 0)
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
            if not p or amount <= 0:
                st["mode"] = None
                return await update.message.reply_text("❌ درخواست شارژ پیدا نشد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            cur = B.db.conn.execute(
                "INSERT INTO topups(partner_id,amount,receipt_file_id,status,created_at) VALUES(?,?,?,?,?)",
                (pid, amount, fid, "pending", B.now()),
            )
            topup_id = cur.lastrowid
            B.db.conn.commit()
            st["mode"] = None
            st.pop("topup_amount", None)
            mk = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید شارژ", callback_data=f"tu:a:{pid}:{amount}:{topup_id}"), InlineKeyboardButton("❌ رد شارژ", callback_data=f"tu:r:{pid}:{amount}:{topup_id}")]])
            text = f"💰 درخواست شارژ حساب\n👤 {p['name']}\n📱 {p['phone']}\n💵 مبلغ: {amount:,} تومان\n🎫 شناسه شارژ: {topup_id}\n📎 رسید پیوست شده است."
            for aid in B.ADM:
                try:
                    await context.bot.send_message(chat_id=int(aid), text=text, reply_markup=mk)
                    try:
                        if update.message.photo:
                            await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"📎 رسید شارژ {topup_id}")
                        else:
                            await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 رسید شارژ {topup_id}")
                    except Exception:
                        log.exception("topup receipt forwarding failed")
                except Exception:
                    log.exception("topup admin notification failed")
            return await update.message.reply_text("✅ رسید دریافت شد و همراه با درخواست شارژ برای مدیریت ارسال شد. پس از تأیید، موجودی شما افزایش می‌یابد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        return await old_media(update, context)
    B.media = media

    # Customer wallet on the home page.
    async def wallet(update, context):
        uid = update.effective_user.id
        key = f"customer_credit_telegram_{uid}"
        raw = B.db.setting(key, "0")
        try:
            credit = int(raw or 0)
        except Exception:
            credit = 0
        return await update.message.reply_text(
            f"💰 اعتبار من\n\nموجودی اعتبار شما: {credit:,} تومان\n\nاگر اعتبار برای حساب شما ثبت شود، از همین بخش قابل مشاهده است.",
            reply_markup=B.main(uid),
        )
    B.customer_wallet = wallet

    # Admin partner balance controls.
    old_amenu = B.amenu
    def amenu():
        base = old_amenu()
        rows = [list(r) for r in base.keyboard]
        if ["➕ افزایش اعتبار", "➖ کاهش اعتبار"] not in rows:
            rows.insert(2, ["➕ افزایش اعتبار", "➖ کاهش اعتبار"])
        return B.kb(rows)
    B.amenu = amenu

    old_router = B.router
    async def router(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        t = (update.message.text or "").strip()

        if t in ("💰 اعتبار من", "💰 کیف پول من", "💰 My wallet", "💰 محفظتي") and not B.admin(uid):
            return await B.customer_wallet(update, context)
        if t == "⬅️ بازگشت" and st.get("status") == "iranian":
            st["status"] = None
            return await update.message.reply_text("لطفاً انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"), InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian")]]))

        if B.admin(uid):
            if t == "➕ افزایش اعتبار":
                st["extra_step"] = "partner_balance_add"
                return await update.message.reply_text("➕ افزایش اعتبار همکار\n\nشماره موبایل همکار و مبلغ را وارد کنید.\nمثال: 09123456789 500000", reply_markup=B.amenu())
            if t == "➖ کاهش اعتبار":
                st["extra_step"] = "partner_balance_sub"
                return await update.message.reply_text("➖ کاهش اعتبار همکار\n\nشماره موبایل همکار و مبلغ را وارد کنید.\nمثال: 09123456789 500000", reply_markup=B.amenu())
            step = st.get("extra_step")
            if step in ("partner_balance_add", "partner_balance_sub"):
                parts = t.replace("،", " ").split()
                phone = None
                amount = None
                for part in parts:
                    a = _amount(part)
                    if a and amount is None:
                        amount = a
                    elif re.fullmatch(r"(?:\+98|0098)?9\d{9}", part) or re.fullmatch(r"09\d{9}", part):
                        phone = part
                if not phone or not amount:
                    return await update.message.reply_text("❌ قالب صحیح: شماره همکار + مبلغ\nمثال: 09123456789 500000", reply_markup=B.amenu())
                phone = B.normalize_phone(phone) or phone
                p = B.db.conn.execute("SELECT * FROM partners WHERE phone=?", (phone,)).fetchone()
                if not p:
                    st["extra_step"] = None
                    return await update.message.reply_text("❌ همکار با این شماره پیدا نشد.", reply_markup=B.amenu())
                old_balance = int(p["balance"] or 0)
                new_balance = old_balance + amount if step == "partner_balance_add" else max(0, old_balance - amount)
                B.db.conn.execute("UPDATE partners SET balance=?,updated_at=? WHERE id=?", (new_balance, B.now(), p["id"]))
                B.db.audit("telegram", uid, "partner_balance_add" if step == "partner_balance_add" else "partner_balance_sub", p["id"], f"{old_balance}->{new_balance}")
                B.db.conn.commit()
                st["extra_step"] = None
                sign = "افزایش" if step == "partner_balance_add" else "کاهش"
                return await update.message.reply_text(f"✅ {sign} اعتبار انجام شد.\n👤 {p['name']}\n💰 موجودی جدید: {new_balance:,} تومان", reply_markup=B.amenu())

        return await old_router(update, context)
    B.router = router

    B._business_flow_patch_installed = True
    log.info("business flow patch installed")
