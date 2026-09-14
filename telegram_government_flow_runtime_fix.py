"""Runtime safety patch for the unified Government flow.

Installs deterministic early handlers for all govv2 text/media states.
Passport requests collect three separate images and forward all attachments
together with the complete request details and working admin controls.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
from payment_invoice import invoice_text, invoice_markup


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))


def install(app, B):
    if getattr(B, "_gov_runtime_fix", False):
        return

    cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]])

    def _file_id(msg):
        if msg.photo:
            return msg.photo[-1].file_id, "photo"
        if msg.document:
            return msg.document.file_id, "document"
        return "", ""

    def _type_name(typ):
        return {
            "card": "کارت آمایش",
            "temporary_card": "کارت موقت",
            "passport": "گذرنامه",
            "residence_booklet": "دفترچه اقامت",
        }.get(typ, "-")

    def _admin_text(st, code, amount):
        typ = st.get("gov_doc_type")
        extra = ""
        if typ == "card":
            extra = f"👨‍👩‍👧‍👦 کد خانوار مشترک: {st.get('gov_family_code', '-') }\n"
        elif typ == "passport":
            extra = f"🛂 شماره پاسپورت مشترک: {st.get('gov_identity_number', '-') }\n"
        elif typ == "residence_booklet":
            extra = f"📗 شماره دفترچه اقامت مشترک: {st.get('gov_identity_number', '-') }\n"
        elif typ == "temporary_card":
            extra = f"🪪 شماره کارت موقت مشترک: {st.get('gov_identity_number', '-') }\n"
        return (
            "👔 مدیر — درخواست جدید\n"
            "🆕 حل مشکل سامانه دولت من\n"
            f"🎫 کد پیگیری: {code}\n"
            f"🪪 نوع مدرک: {_type_name(typ)}\n"
            f"📱 شماره موبایل مشترک: {st.get('gov_phone', '-')}\n"
            f"🎂 تاریخ تولد مشترک: {st.get('gov_dob', '-')}\n"
            f"🆔 شناسه یکتای مشترک: {st.get('gov_unique', '-')}\n"
            f"🔖 شناسه اختصاصی مشترک: {st.get('gov_special', '-')}\n"
            + extra
            + f"📮 کد پستی مشترک: {st.get('gov_postal', '-')}\n"
            + f"💰 مبلغ: {amount:,} تومان\n"
            + "💳 وضعیت پرداخت: در انتظار پرداخت فاکتور\n"
            + "📎 پیوست‌ها: در ادامه همین درخواست ارسال می‌شوند."
        )

    def _controls(rid):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"rq:detail:{rid}")],
            [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"rq:ask:{rid}")],
            [
                InlineKeyboardButton("💰 تأیید دریافت وجه", callback_data=f"rq:payconfirm:{rid}"),
                InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"rq:review:{rid}"),
            ],
            [InlineKeyboardButton("❌ رد درخواست", callback_data=f"rq:reject:{rid}")],
        ])

    async def text(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if not str(mode or "").startswith("govv2_"):
            return
        t = (update.message.text or "").strip()
        d = _digits(t)

        if mode == "govv2_phone":
            p = re.sub(r"\D", "", d)
            if p.startswith("98"):
                p = "0" + p[2:]
            if not re.fullmatch(r"09\d{9}", p):
                await update.message.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.", reply_markup=cancel)
            else:
                st["gov_phone"] = p
                st["mode"] = "govv2_dob"
                await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_dob":
            st["gov_dob"] = t
            st["mode"] = "govv2_unique"
            await update.message.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_unique":
            if len(t) < 3:
                await update.message.reply_text("❌ شناسه یکتا را صحیح وارد کنید.", reply_markup=cancel)
            else:
                st["gov_unique"] = t
                st["mode"] = "govv2_special"
                await update.message.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_special":
            if not re.fullmatch(r"1\d{11}", d):
                await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.", reply_markup=cancel)
            else:
                st["gov_special"] = d
                typ = st.get("gov_doc_type")
                if typ == "card":
                    st["mode"] = "govv2_family"
                    await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (فقط برای کارت آمایش):", reply_markup=cancel)
                else:
                    st["mode"] = "govv2_identity_number"
                    prompt = (
                        "🛂 شماره گذرنامه مشترک را وارد کنید:" if typ == "passport" else
                        "📗 شماره دفترچه اقامت مشترک را وارد کنید:" if typ == "residence_booklet" else
                        "🪪 شماره کارت موقت مشترک را وارد کنید:"
                    )
                    await update.message.reply_text(prompt, reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_family":
            if not d.isdigit():
                await update.message.reply_text("❌ کد خانوار باید عددی باشد.", reply_markup=cancel)
            else:
                st["gov_family_code"] = d
                st["mode"] = "govv2_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_identity_number":
            if len(t) < 3:
                await update.message.reply_text("❌ شماره مدرک را صحیح وارد کنید.", reply_markup=cancel)
            else:
                st["gov_identity_number"] = t
                st["mode"] = "govv2_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_postal":
            if not re.fullmatch(r"\d{10}", d):
                await update.message.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.", reply_markup=cancel)
            else:
                st["gov_postal"] = d
                if st.get("gov_doc_type") == "passport":
                    st["mode"] = "govv2_passport_photo1"
                    await update.message.reply_text("📸 ۱/۳ — لطفاً عکس صفحه اول پاسپورت مشترک را ارسال کنید:", reply_markup=cancel)
                else:
                    st["mode"] = "govv2_photo"
                    await update.message.reply_text("📸 حالا تصویر مدرک مشترک را ارسال کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop

    async def _create_request(update, context, st, attachments):
        msg = update.message
        amount = int(B.db.setting("price_government", "500000") or 500000)
        pid = st.get("partner_id")
        owner = pid or B.db.user("telegram", update.effective_user.id, update.effective_user.username, update.effective_user.full_name)
        rid, code = B.db.create_request(owner, "government", "telegram", amount)
        typ = st.get("gov_doc_type")
        fields = [
            ("doc_type", typ),
            ("phone", st.get("gov_phone")),
            ("dob", st.get("gov_dob")),
            ("unique_id", st.get("gov_unique")),
            ("special_id", st.get("gov_special")),
            ("postal_code", st.get("gov_postal")),
        ]
        if typ == "card":
            fields.append(("family_code", st.get("gov_family_code")))
        if typ == "passport":
            fields.append(("passport", st.get("gov_identity_number")))
        elif typ == "temporary_card":
            fields.append(("temporary_card_number", st.get("gov_identity_number")))
        elif typ == "residence_booklet":
            fields.append(("booklet_number", st.get("gov_identity_number")))
        if pid:
            fields.append(("partner_id", str(pid)))
        for k, v in fields:
            if v:
                B.db.answer(rid, k, answer=v)

        # Keep the legacy document attachment and add named attachments for every
        # passport image so the detail view can display all three reliably.
        labels = ["document"] if typ != "passport" else [
            "passport_first_page", "passport_visa_renewal", "passport_renewal"
        ]
        for key, fid in zip(labels, attachments):
            B.db.answer(rid, key, file_id=fid)
        if typ == "passport" and attachments:
            B.db.answer(rid, "document", file_id=attachments[0])

        B.db.conn.execute(
            "UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='invoice',updated_at=? WHERE id=?",
            (B.now(), rid),
        )
        B.db.conn.commit()

        text_msg = _admin_text(st, code, amount)
        controls = _controls(rid)
        for aid in B.ADM:
            try:
                await context.bot.send_message(chat_id=int(aid), text=text_msg, reply_markup=controls)
                if typ == "passport":
                    captions = [
                        "📸 ۱/۳ — صفحه اول پاسپورت",
                        "📸 ۲/۳ — صفحه تمدید روادید",
                        "📸 ۳/۳ — صفحه تمدید گذرنامه",
                    ]
                    for fid, caption in zip(attachments, captions):
                        try:
                            await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"🎫 {code}\n{caption}")
                        except Exception:
                            try:
                                await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"🎫 {code}\n{caption}")
                            except Exception:
                                pass
                else:
                    fid = attachments[0]
                    try:
                        await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"🎫 {code}\n📎 تصویر مدرک مشترک")
                    except Exception:
                        try:
                            await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"🎫 {code}\n📎 تصویر مدرک مشترک")
                        except Exception:
                            pass
            except Exception:
                pass

        st["mode"] = "invoice_pending"
        st["request_id"] = rid
        st["tracking_code"] = code
        await msg.reply_text(
            invoice_text("فاکتور خدمات حل مشکل سامانه دولت من", amount, code, B),
            reply_markup=invoice_markup(B),
            parse_mode="HTML",
        )
        raise ApplicationHandlerStop

    async def media(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if mode not in {"govv2_photo", "govv2_passport_photo1", "govv2_passport_photo2", "govv2_passport_photo3"}:
            return
        msg = update.message
        fid, kind = _file_id(msg)
        if not fid:
            await msg.reply_text("❌ لطفاً عکس یا فایل مدرک را ارسال کنید.", reply_markup=cancel)
            raise ApplicationHandlerStop

        if mode == "govv2_passport_photo1":
            st["gov_passport_photo1"] = fid
            st["mode"] = "govv2_passport_photo2"
            await msg.reply_text("📸 ۲/۳ — لطفاً عکس صفحه تمدید روادید را ارسال کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_passport_photo2":
            st["gov_passport_photo2"] = fid
            st["mode"] = "govv2_passport_photo3"
            await msg.reply_text("📸 ۳/۳ — لطفاً عکس تمدید گذرنامه را ارسال کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_passport_photo3":
            st["gov_passport_photo3"] = fid
            await _create_request(update, context, st, [
                st.get("gov_passport_photo1"),
                st.get("gov_passport_photo2"),
                st.get("gov_passport_photo3"),
            ])
            raise ApplicationHandlerStop

        await _create_request(update, context, st, [fid])
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-80)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, media), group=-80)
    B._gov_runtime_fix = True
