"""Stable Government access document flow.

Keeps the government service flow deterministic and isolated from legacy
handlers. Supports Amayesh card, temporary card, passport and residence
booklet. Optional SIM-card proof is collected after the required document images.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop
from payment_invoice import invoice_text, invoice_markup

CANCEL = "govv3:cancel"


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _cancel_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data=CANCEL)]])


def _doc_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪪 کارت آمایش", callback_data="govv3:card"), InlineKeyboardButton("🪪 کارت موقت", callback_data="govv3:temporary")],
        [InlineKeyboardButton("🛂 گذرنامه", callback_data="govv3:passport"), InlineKeyboardButton("📗 دفترچه اقامت", callback_data="govv3:residence")],
        [InlineKeyboardButton("❌ انصراف", callback_data=CANCEL)],
    ])


def _optional_sim_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 ارسال سند سیم‌کارت", callback_data="govv3:sim_yes")],
        [InlineKeyboardButton("⏭ بدون سند سیم‌کارت", callback_data="govv3:sim_no")],
        [InlineKeyboardButton("❌ انصراف", callback_data=CANCEL)],
    ])


def _type_name(t):
    return {"card": "کارت آمایش", "temporary_card": "کارت موقت", "passport": "گذرنامه", "residence_booklet": "دفترچه اقامت"}.get(t, "-")


def _file_id(msg):
    if msg.photo:
        return msg.photo[-1].file_id
    if msg.document:
        return msg.document.file_id
    return ""


def _stable_main(B, uid):
    rows = [
        ["🏛 حل مشکل سامانه دولت من"],
        ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
        ["🎫 کد رهگیری تمدید کارت‌ها", "📱 خدمات سیم کارت"],
        ["📝 آزمون غربالگری", "🎫 پیگیری"],
        ["💰 کیف پول من", "📞 تماس با ما"],
        ["📝 ثبت شکایت مشتریان"],
        ["👥 پنل همکاران"],
    ]
    if B.admin(uid):
        rows.append(["🛠 پنل مدیریت بات"])
    return B.kb(rows)


def install(app, B):
    if getattr(B, "_gov_documents_v3", False):
        return
    old_main = getattr(B, "main", None)
    B._gov_old_main = old_main
    B.main = lambda uid: _stable_main(B, uid)

    async def start(update, context):
        uid = update.effective_user.id
        old = B.S.get(uid, {})
        B.S[uid] = {
            "mode": "govv3_doc_type",
            "lang": old.get("lang", "fa"),
            "partner_id": old.get("partner_id"),
            "gov_files": {},
        }
        return await update.effective_message.reply_text(
            "🏛 حل مشکل سامانه دولت من\n\n🪪 نوع مدرک مشترک را انتخاب کنید:",
            reply_markup=_doc_markup(),
        )

    B.gov = start

    async def cancel(update, context, st):
        uid = update.effective_user.id
        partner_id = st.get("partner_id")
        lang = st.get("lang", "fa")
        st.clear()
        st.update({"status": "foreign", "lang": lang})
        if partner_id:
            st["partner_id"] = partner_id
            st["partner_active"] = True
            return await update.effective_message.reply_text("❌ عملیات لغو شد.", reply_markup=B.partner_kb(lang))
        return await update.effective_message.reply_text("❌ عملیات لغو شد.", reply_markup=_stable_main(B, uid))

    async def cb(update, context):
        q = update.callback_query
        if not q or not str(q.data or "").startswith("govv3:"):
            return
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        action = str(q.data).split(":", 1)[1]
        if action == "cancel":
            await cancel(q, context, st)
            raise ApplicationHandlerStop
        if action in {"card", "temporary", "passport", "residence"}:
            typ = {"card": "card", "temporary": "temporary_card", "passport": "passport", "residence": "residence_booklet"}[action]
            st["gov_doc_type"] = typ
            st["mode"] = "govv3_phone"
            await q.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if action == "sim_yes":
            st["mode"] = "govv3_sim_optional"
            await q.message.reply_text("📱 لطفاً سند سیم‌کارت مشترک را ارسال کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if action == "sim_no":
            await _create_request(update, context, st)
            raise ApplicationHandlerStop

    async def text(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if not str(mode or "").startswith("govv3_"):
            return
        t = (update.message.text or "").strip()
        d = _digits(t)
        if mode == "govv3_phone":
            p = re.sub(r"\D", "", d)
            if p.startswith("98") and len(p) == 12:
                p = "0" + p[2:]
            if not re.fullmatch(r"09\d{9}", p):
                await update.message.reply_text("❌ شماره موبایل باید دقیقاً ۱۱ رقم و با ۰۹ شروع شود.", reply_markup=_cancel_markup())
            else:
                st["gov_phone"] = p
                st["mode"] = "govv3_dob"
                await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_dob":
            if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", d):
                await update.message.reply_text("❌ تاریخ تولد نامعتبر است. مثال صحیح: 1385/05/12", reply_markup=_cancel_markup())
            else:
                st["gov_dob"] = d
                st["mode"] = "govv3_unique"
                await update.message.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_unique":
            if not re.fullmatch(r"9\d{9}", d):
                await update.message.reply_text("❌ شناسه یکتا باید دقیقاً ۱۰ رقم و با ۹ شروع شود.", reply_markup=_cancel_markup())
            else:
                st["gov_unique"] = d
                st["mode"] = "govv3_special"
                await update.message.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_special":
            if not re.fullmatch(r"1\d{11}", d):
                await update.message.reply_text("❌ شناسه اختصاصی باید دقیقاً ۱۲ رقم و با ۱ شروع شود.", reply_markup=_cancel_markup())
            else:
                st["gov_special"] = d
                typ = st.get("gov_doc_type")
                if typ in {"card", "temporary_card"}:
                    st["mode"] = "govv3_family"
                    await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (حداقل ۵ رقم):", reply_markup=_cancel_markup())
                else:
                    st["mode"] = "govv3_identity_number"
                    prompt = {"passport": "🛂 شماره گذرنامه مشترک را وارد کنید:", "residence_booklet": "📗 شماره دفترچه اقامت مشترک را وارد کنید:"}[typ]
                    await update.message.reply_text(prompt, reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_family":
            if not re.fullmatch(r"\d{5,}", d):
                await update.message.reply_text("❌ کد خانوار نامعتبر است. کد خانوار باید عددی و حداقل ۵ رقم باشد.", reply_markup=_cancel_markup())
            else:
                st["gov_family_code"] = d
                st["mode"] = "govv3_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_identity_number":
            if not re.fullmatch(r"\d{3,}", d):
                await update.message.reply_text("❌ شماره مدرک را صحیح وارد کنید.", reply_markup=_cancel_markup())
            else:
                st["gov_identity_number"] = d
                st["mode"] = "govv3_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_postal":
            if not re.fullmatch(r"\d{10}", d):
                await update.message.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.", reply_markup=_cancel_markup())
            else:
                st["gov_postal"] = d
                typ = st.get("gov_doc_type")
                if typ == "passport":
                    st["mode"] = "govv3_passport_photo1"
                    await update.message.reply_text("📸 ۱/۳ — عکس صفحه اول پاسپورت مشترک را ارسال کنید:", reply_markup=_cancel_markup())
                elif typ == "residence_booklet":
                    st["mode"] = "govv3_residence_photo1"
                    await update.message.reply_text("📗 ۱/۲ — عکس اول دفترچه اقامت مشترک را ارسال کنید:", reply_markup=_cancel_markup())
                else:
                    st["mode"] = "govv3_card_photo"
                    await update.message.reply_text("🪪 ۱/۱ — عکس مدرک مشترک را ارسال کنید:", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop

    async def media(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if not str(mode or "").startswith("govv3_"):
            return
        fid = _file_id(update.message)
        if not fid:
            await update.message.reply_text("❌ لطفاً عکس یا فایل مدرک را ارسال کنید.", reply_markup=_cancel_markup())
            raise ApplicationHandlerStop
        if mode == "govv3_passport_photo1":
            st["gov_passport_photo1"] = fid; st["mode"] = "govv3_passport_photo2"
            await update.message.reply_text("📸 ۲/۳ — عکس صفحه تمدید پاسپورت را ارسال کنید:", reply_markup=_cancel_markup())
        elif mode == "govv3_passport_photo2":
            st["gov_passport_photo2"] = fid; st["mode"] = "govv3_passport_photo3"
            await update.message.reply_text("📸 ۳/۳ — عکس صفحه تمدید/روادید پاسپورت را ارسال کنید:", reply_markup=_cancel_markup())
        elif mode == "govv3_passport_photo3":
            st["gov_passport_photo3"] = fid; st["mode"] = "govv3_sim_optional"
            await update.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است.\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:", reply_markup=_optional_sim_markup())
        elif mode == "govv3_residence_photo1":
            st["gov_residence_photo1"] = fid; st["mode"] = "govv3_residence_photo2"
            await update.message.reply_text("📗 ۲/۲ — عکس دوم دفترچه اقامت مشترک را ارسال کنید:", reply_markup=_cancel_markup())
        elif mode == "govv3_residence_photo2":
            st["gov_residence_photo2"] = fid; st["mode"] = "govv3_sim_optional"
            await update.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است.\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:", reply_markup=_optional_sim_markup())
        elif mode == "govv3_card_photo":
            st["gov_card_photo"] = fid; st["mode"] = "govv3_sim_optional"
            await update.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است.\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:", reply_markup=_optional_sim_markup())
        elif mode == "govv3_sim_optional":
            st["gov_sim_document"] = fid
            await _create_request(update, context, st)
        else:
            return
        raise ApplicationHandlerStop

    async def _create_request(update, context, st):
        uid = update.effective_user.id
        amount = int(B.db.setting("price_government", "500000") or 500000)
        pid = st.get("partner_id")
        owner = pid or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
        rid, code = B.db.create_request(owner, "government", "telegram", amount)
        typ = st.get("gov_doc_type")
        fields = [("doc_type", typ), ("phone", st.get("gov_phone")), ("dob", st.get("gov_dob")), ("unique_id", st.get("gov_unique")), ("special_id", st.get("gov_special")), ("postal_code", st.get("gov_postal"))]
        if typ in {"card", "temporary_card"}: fields.append(("family_code", st.get("gov_family_code")))
        if typ == "passport": fields.append(("passport", st.get("gov_identity_number")))
        if typ == "residence_booklet": fields.append(("booklet_number", st.get("gov_identity_number")))
        if pid: fields.append(("partner_id", str(pid)))
        for k, v in fields:
            if v: B.db.answer(rid, k, answer=v)
        if typ == "passport":
            attachments = [st.get("gov_passport_photo1"), st.get("gov_passport_photo2"), st.get("gov_passport_photo3")]
            labels = ["passport_first_page", "passport_renewal_page", "passport_visa_renewal_page"]
        elif typ == "residence_booklet":
            attachments = [st.get("gov_residence_photo1"), st.get("gov_residence_photo2")]
            labels = ["residence_first_page", "residence_renewal_page"]
        else:
            attachments = [st.get("gov_card_photo")]
            labels = ["document"]
        for key, fid in zip(labels, attachments):
            if fid: B.db.answer(rid, key, file_id=fid)
        if st.get("gov_sim_document"):
            B.db.answer(rid, "sim_card_document", file_id=st["gov_sim_document"])
        B.db.conn.execute("UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='invoice',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
        extra = ""
        if typ in {"card", "temporary_card"}: extra = f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family_code','-')}\n"
        elif typ == "passport": extra = f"🛂 شماره گذرنامه: {st.get('gov_identity_number','-')}\n"
        elif typ == "residence_booklet": extra = f"📗 شماره دفترچه اقامت: {st.get('gov_identity_number','-')}\n"
        text = ("👔 مدیر — درخواست جدید\n🆕 حل مشکل سامانه دولت من\n" f"🎫 کد پیگیری: {code}\n🪪 نوع مدرک: {_type_name(typ)}\n" f"📱 شماره موبایل مشترک: {st.get('gov_phone','-')}\n🎂 تاریخ تولد مشترک: {st.get('gov_dob','-')}\n" f"🆔 شناسه یکتای مشترک: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی مشترک: {st.get('gov_special','-')}\n" + extra + f"📮 کد پستی مشترک: {st.get('gov_postal','-')}\n" f"📱 سند سیم‌کارت: {'ارسال شده' if st.get('gov_sim_document') else 'اختیاری — ارسال نشده'}\n" f"💰 مبلغ: {amount:,} تومان\n💳 وضعیت پرداخت: در انتظار پرداخت فاکتور")
        controls = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"rq:detail:{rid}")],
            [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"rq:ask:{rid}")],
            [InlineKeyboardButton("💰 تأیید دریافت وجه", callback_data=f"rq:payconfirm:{rid}"), InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"rq:review:{rid}")],
            [InlineKeyboardButton("❌ رد درخواست", callback_data=f"rq:reject:{rid}")],
        ])
        if typ == "passport": captions = ["📸 ۱/۳ — صفحه اول پاسپورت", "📸 ۲/۳ — صفحه تمدید پاسپورت", "📸 ۳/۳ — صفحه تمدید روادید"]
        elif typ == "residence_booklet": captions = ["📗 ۱/۲ — صفحه اول مشخصات دفترچه اقامت", "📗 ۲/۲ — صفحه تمدید دفترچه اقامت"]
        else: captions = [f"🪪 تصویر {_type_name(typ)}"]
        for aid in B.ADM:
            try:
                await context.bot.send_message(chat_id=int(aid), text=text, reply_markup=controls)
            except Exception:
                pass
            for fid, cap in zip(attachments, captions):
                if not fid: continue
                try: await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"🎫 {code}\n{cap}")
                except Exception:
                    try: await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"🎫 {code}\n{cap}")
                    except Exception: pass
            if st.get("gov_sim_document"):
                try: await context.bot.send_photo(chat_id=int(aid), photo=st["gov_sim_document"], caption=f"🎫 {code}\n📱 سند سیم‌کارت اختیاری")
                except Exception:
                    try: await context.bot.send_document(chat_id=int(aid), document=st["gov_sim_document"], caption=f"🎫 {code}\n📱 سند سیم‌کارت اختیاری")
                    except Exception: pass
        st["mode"] = "invoice_pending"; st["request_id"] = rid; st["tracking_code"] = code
        await update.effective_message.reply_text(invoice_text("فاکتور خدمات حل مشکل سامانه دولت من", amount, code, B), reply_markup=invoice_markup(B), parse_mode="HTML")

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^govv3:"), group=-120)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-120)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, media), group=-120)
    B._gov_documents_v3 = True
