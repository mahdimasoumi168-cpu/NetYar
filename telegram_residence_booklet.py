"""Residence booklet flow for the government-login service.

The residence booklet follows the passport-style identity collection, but asks
for the booklet number instead of a passport number. It is isolated so the
existing card/passport flow remains unchanged.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))


def _cancel(B):
    return B.cancel_kb("fa")


async def _start_from_ui(update, context, B):
    q = update.callback_query
    if not q or not q.data.startswith("ui:"):
        return
    label = q.data[3:]
    if "حل مشکل سامانه دولت من" not in label:
        if not (B.admin(q.from_user.id) and "پنل مدیریت بات" in label):
            return
    await q.answer()
    uid = q.from_user.id
    old = dict(B.S.get(uid, {}))
    B.S[uid] = {
        "mode": "gov_doc_type",
        "lang": old.get("lang", "fa"),
        "gov_files": {},
        "partner_id": old.get("partner_id"),
    }
    return await q.message.reply_text(
        "🪪 نوع مدرک مشترک را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            [["🪪 کارت آمایش", "🛂 گذرنامه"], ["📗 دفترچه اقامت"], ["❌ انصراف"]],
            resize_keyboard=True,
        ),
    )


async def _residence_text(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    text = (update.message.text or "").strip()
    digits = _digits(text).replace(" ", "").replace("-", "")

    if mode == "gov_doc_type" and text == "📗 دفترچه اقامت":
        st["gov_doc_type"] = "residence_booklet"
        st["mode"] = "gov_phone"
        return await update.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:", reply_markup=_cancel(B))

    if st.get("gov_doc_type") != "residence_booklet":
        return

    # The normal UX module collects phone, DOB, unique ID and special ID.
    # We only take over at the two points that differ for the booklet.
    if mode == "gov_special":
        if not re.fullmatch(r"1\d{11}", digits):
            return await update.message.reply_text(
                "❌ شناسه اختصاصی صحیح نیست.\nشناسه اختصاصی باید دقیقاً ۱۲ رقم باشد و با عدد ۱ شروع شود.",
                reply_markup=_cancel(B),
            )
        st["gov_special"] = digits
        st["mode"] = "gov_family"
        return await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید:", reply_markup=_cancel(B))

    if mode == "gov_family":
        if not re.fullmatch(r"\d{1,20}", digits):
            return await update.message.reply_text("❌ کد خانوار باید عددی باشد.", reply_markup=_cancel(B))
        st["gov_family_code"] = digits
        st["mode"] = "gov_booklet_number"
        return await update.message.reply_text("📗 شماره دفترچه اقامت مشترک را وارد کنید:", reply_markup=_cancel(B))

    if mode == "gov_booklet_number":
        if len(text) < 3:
            return await update.message.reply_text("❌ شماره دفترچه اقامت را صحیح وارد کنید.", reply_markup=_cancel(B))
        st["gov_booklet_number"] = text
        st["mode"] = "gov_postal"
        return await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=_cancel(B))


async def _residence_media(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("mode") != "gov_photo" or st.get("gov_doc_type") != "residence_booklet":
        return
    fid = update.message.photo[-1].file_id if update.message.photo else (update.message.document.file_id if update.message.document else "")
    if not fid:
        return await update.message.reply_text("❌ عکس یا فایل معتبر ارسال کنید.", reply_markup=_cancel(B))

    amount = int(B.db.setting("price_government", "500000") or 500000)
    pid = st.get("partner_id")
    p = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone() if pid else None
    if pid and (not p or int(p["balance"] or 0) < amount):
        return await update.message.reply_text(
            f"❌ اعتبار کافی نیست.\n💰 هزینه خدمت: {amount:,} تومان\n💳 اعتبار فعلی: {int(p['balance'] if p else 0):,} تومان\n\nلطفاً ابتدا حساب را شارژ کنید.",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )

    owner = pid or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
    rid, code = B.db.create_request(owner, "government", "telegram", amount)
    fields = [
        ("doc_type", "residence_booklet"),
        ("phone", st.get("gov_phone", st.get("phone", ""))),
        ("dob", st.get("dob", "")),
        ("unique_id", st.get("gov_unique", st.get("unique_id", ""))),
        ("special_id", st.get("gov_special", "")),
        ("family_code", st.get("gov_family_code", "")),
        ("booklet_number", st.get("gov_booklet_number", "")),
        ("postal_code", st.get("postal_code", "")),
    ]
    for key, value in fields:
        if value:
            B.db.answer(rid, key, answer=value)
    B.db.answer(rid, "document", file_id=fid)

    if pid:
        B.db.conn.execute(
            "UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",
            (B.now(), rid),
        )
        B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?", (amount, B.now(), pid))
        B.db.conn.commit()
        left = int(p["balance"]) - amount
    else:
        B.db.conn.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.commit()
        left = None

    text = (
        "👔 مدیر — اعلان خدمات جدید\n\n"
        "🆕 حل مشکل سامانه دولت من\n"
        f"🎫 کد پیگیری: {code}\n"
        "🪪 نوع مدرک: دفترچه اقامت\n"
        f"📱 موبایل مشترک: {st.get('gov_phone', st.get('phone', '-'))}\n"
        f"🎂 تاریخ تولد: {st.get('dob', '-')}\n"
        f"🆔 شناسه یکتا: {st.get('gov_unique', st.get('unique_id', '-'))}\n"
        f"🔖 شناسه اختصاصی: {st.get('gov_special', '-')}\n"
        f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family_code', '-')}\n"
        f"📗 شماره دفترچه اقامت: {st.get('gov_booklet_number', '-')}\n"
        f"📮 کد پستی منزل: {st.get('postal_code', '-')}\n"
        f"💰 مبلغ خدمت: {amount:,} تومان\n"
        + (f"💳 کسر از اعتبار همکار: {amount:,} تومان\n💵 اعتبار باقی‌مانده: {left:,} تومان\n" if pid else "")
        + "📎 تصویر دفترچه اقامت در همین اعلان پیوست شده است."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده کامل درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"), InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"), InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])
    for aid in B.ADM:
        try:
            if update.message.photo:
                await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=text, reply_markup=markup)
            else:
                await context.bot.send_document(chat_id=int(aid), document=fid, caption=text, reply_markup=markup)
        except Exception:
            pass
    st["mode"] = None
    if pid:
        return await update.message.reply_text(
            f"✅ درخواست با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ کسرشده: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
    return await update.message.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}", reply_markup=B.main(uid))


def install(app, B):
    # Run before the generic UI/text/media handlers.
    app.add_handler(CallbackQueryHandler(lambda u,c: _start_from_ui(u,c,B), pattern=r"^ui:"), group=-5)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: _residence_text(u,c,B)), group=-5)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, lambda u,c: _residence_media(u,c,B)), group=-5)
