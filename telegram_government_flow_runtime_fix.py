"""Deterministic runtime guard for the unified Government service flow."""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
from payment_invoice import invoice_text, invoice_markup

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def _digits(v):
    return str(v or "").translate(_DIGITS)

def install(app, B):
    if getattr(B, "_gov_runtime_fix", False):
        return
    cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]])

    def _file_id(msg):
        if getattr(msg, "photo", None):
            return msg.photo[-1].file_id
        if getattr(msg, "document", None):
            return msg.document.file_id
        return ""

    def _type_name(typ):
        return {"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}.get(typ, "-")

    def _admin_text(st, code, amount, reused=False, previous_code=""):
        typ = st.get("gov_doc_type")
        extra = ""
        if typ == "card": extra = f"👨‍👩‍👧‍👦 کد خانوار مشترک: {st.get('gov_family_code','-')}\n"
        elif typ == "passport": extra = f"🛂 شماره پاسپورت مشترک: {st.get('gov_identity_number','-')}\n"
        elif typ == "residence_booklet": extra = f"📗 شماره دفترچه اقامت مشترک: {st.get('gov_identity_number','-')}\n"
        elif typ == "temporary_card": extra = f"🪪 شماره کارت موقت مشترک: {st.get('gov_identity_number','-')}\n"
        payment_line = "♻️ هزینه جدید: ۰ تومان؛ شناسه قبلاً پرداخت شده است" if reused else f"💰 مبلغ: {amount:,} تومان\n💳 وضعیت پرداخت: در انتظار پرداخت فاکتور"
        if reused and previous_code: payment_line += f"\n📌 درخواست پرداخت‌شده قبلی: {previous_code}"
        return ("👔 مدیر — درخواست جدید\n🆕 حل مشکل سامانه دولت من\n"
                f"🎫 کد پیگیری: {code}\n🪪 نوع مدرک: {_type_name(typ)}\n"
                f"📱 شماره موبایل مشترک: {st.get('gov_phone','-')}\n"
                f"🎂 تاریخ تولد مشترک: {st.get('gov_dob','-')}\n"
                f"🆔 شناسه یکتای مشترک: {st.get('gov_unique','-')}\n"
                f"🔖 شناسه اختصاصی مشترک: {st.get('gov_special','-')}\n" + extra +
                f"📮 کد پستی مشترک: {st.get('gov_postal','-')}\n" + payment_line +
                "\n📎 تمام پیوست‌ها در ادامه همین درخواست ارسال می‌شوند.")

    def _controls(rid):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"rq:detail:{rid}")],
            [InlineKeyboardButton("🔐 درخواست کد امنیتی از همکار", callback_data=f"rq:ask:{rid}")],
            [InlineKeyboardButton("💰 تأیید دریافت وجه", callback_data=f"rq:payconfirm:{rid}"), InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"rq:review:{rid}")],
            [InlineKeyboardButton("❌ رد درخواست", callback_data=f"rq:reject:{rid}")],
        ])

    def _find_paid_by_special(owner, special_id):
        if not owner or not special_id: return None
        return B.db.conn.execute(
            """SELECT r.id,r.tracking_code,r.status,r.payment_status
               FROM requests r JOIN request_answers a ON a.request_id=r.id
               WHERE r.user_id=? AND r.service_key='government'
                 AND r.payment_status='paid' AND a.field_key='special_id' AND a.answer=?
               ORDER BY r.id DESC LIMIT 1""", (owner, special_id)).fetchone()

    async def text(update, context):
        if not update.message: return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if not str(mode or "").startswith("govv2_"): return
        t = (update.message.text or "").strip()
        d = _digits(t)
        if mode == "govv2_phone":
            p = re.sub(r"\D", "", d)
            if p.startswith("98"): p = "0" + p[2:]
            if not re.fullmatch(r"09\d{9}", p):
                await update.message.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.", reply_markup=cancel)
            else:
                st["gov_phone"] = p; st["mode"] = "govv2_dob"
                await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_dob":
            st["gov_dob"] = t; st["mode"] = "govv2_unique"
            await update.message.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:", reply_markup=cancel); raise ApplicationHandlerStop
        if mode == "govv2_unique":
            if len(t) < 3:
                await update.message.reply_text("❌ شناسه یکتا را صحیح وارد کنید.", reply_markup=cancel)
            else:
                st["gov_unique"] = t; st["mode"] = "govv2_special"
                await update.message.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_special":
            if not re.fullmatch(r"1\d{11}", d):
                await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.", reply_markup=cancel)
            else:
                st["gov_special"] = d; typ = st.get("gov_doc_type")
                if typ == "card":
                    st["mode"] = "govv2_family"; prompt = "👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (فقط برای کارت آمایش):"
                else:
                    st["mode"] = "govv2_identity_number"
                    prompt = "🛂 شماره گذرنامه مشترک را وارد کنید:" if typ == "passport" else "📗 شماره دفترچه اقامت مشترک را وارد کنید:" if typ == "residence_booklet" else "🪪 شماره کارت موقت مشترک را وارد کنید:"
                await update.message.reply_text(prompt, reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_family":
            if not d.isdigit():
                await update.message.reply_text("❌ کد خانوار باید عددی باشد.", reply_markup=cancel)
            else:
                st["gov_family_code"] = d; st["mode"] = "govv2_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_identity_number":
            if len(t) < 3:
                await update.message.reply_text("❌ شماره مدرک را صحیح وارد کنید.", reply_markup=cancel)
            else:
                st["gov_identity_number"] = t; st["mode"] = "govv2_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode == "govv2_postal":
            if not re.fullmatch(r"\d{10}", d):
                await update.message.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.", reply_markup=cancel)
            else:
                st["gov_postal"] = d
                if st.get("gov_doc_type") == "passport":
                    st["mode"] = "govv2_passport_photo1"; prompt = "📸 ۱/۳ — لطفاً عکس صفحه اول پاسپورت مشترک را ارسال کنید:"
                else:
                    st["mode"] = "govv2_photo"; prompt = "📸 حالا تصویر مدرک مشترک را ارسال کنید:"
                await update.message.reply_text(prompt, reply_markup=cancel)
            raise ApplicationHandlerStop

    async def _create_request(update, context, st, attachments):
        msg = update.message
        uid = update.effective_user.id
        amount = int(B.db.setting("price_government", "500000") or 500000)
        pid = st.get("partner_id")
        owner = pid or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
        special_id = _digits(st.get("gov_special"))
        previous = _find_paid_by_special(owner, special_id)

        # Build the request only after deciding the payment route. Partners pay
        # from balance; customers receive an invoice and the request stays
        # unpaid until a receipt is submitted and management confirms it.
        if not previous and pid:
            try:
                conn = B.db.conn
                conn.execute("BEGIN IMMEDIATE")
                p = conn.execute("SELECT id,name,balance,active FROM partners WHERE id=? AND active=1", (int(pid),)).fetchone()
                bal = int(p["balance"] or 0) if p else 0
                if not p or bal < amount:
                    conn.rollback()
                    need = max(0, amount - bal)
                    await msg.reply_text(
                        f"❌ اعتبار پنل همکاران کافی نیست.\\n\\n"
                        f"💳 اعتبار فعلی: {bal:,} تومان\\n"
                        f"💰 هزینه خدمت: {amount:,} تومان\\n"
                        f"➕ مبلغ موردنیاز برای شارژ: {need:,} تومان\\n\\n"
                        "ابتدا حساب همکار را شارژ کنید؛ تا پرداخت انجام نشود درخواست برای مدیریت ارسال نمی‌شود.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ شارژ حساب", callback_data="topupui:start")],
                            [InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]
                        ]),
                    )
                    return
                cur = conn.execute(
                    "UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?",
                    (amount, B.now(), int(pid), amount),
                )
                if cur.rowcount != 1:
                    conn.rollback()
                    await msg.reply_text("❌ کسر اعتبار در همین لحظه انجام نشد؛ مبلغی کسر نشده است. دوباره تلاش کنید.", reply_markup=B.partner_kb(st.get("lang","fa")))
                    return
                rid, code = B.db.create_request(owner, "government", "telegram", amount)
                conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?", (B.now(), rid))
                conn.commit()
            except Exception:
                try: B.db.conn.rollback()
                except Exception: pass
                raise
        elif previous:
            rid, code = B.db.create_request(owner, "government", "telegram", 0)
        else:
            rid, code = B.db.create_request(owner, "government", "telegram", amount)

        typ = st.get("gov_doc_type")
        fields = [
            ("doc_type",typ),("phone",st.get("gov_phone")),("dob",st.get("gov_dob")),
            ("unique_id",st.get("gov_unique")),("special_id",special_id),("postal_code",st.get("gov_postal"))
        ]
        if typ == "card": fields.append(("family_code",st.get("gov_family_code")))
        if typ == "passport": fields.append(("passport",st.get("gov_identity_number")))
        elif typ == "temporary_card": fields.append(("temporary_card_number",st.get("gov_identity_number")))
        elif typ == "residence_booklet": fields.append(("booklet_number",st.get("gov_identity_number")))
        if pid: fields.append(("partner_id",str(pid)))
        for k,v in fields:
            if v: B.db.answer(rid,k,answer=v)

        labels = ["document"] if typ != "passport" else ["passport_first_page","passport_visa_renewal","passport_renewal"]
        for key,fid in zip(labels,attachments):
            if fid: B.db.answer(rid,key,file_id=fid)

        if previous:
            B.db.conn.execute(
                "UPDATE requests SET status='submitted',payment_status='paid',payment_method='previous_government_request',payment_note=?,updated_at=? WHERE id=?",
                (f"هزینه قبلاً برای شناسه اختصاصی {special_id} پرداخت شده است؛ درخواست مجدد بدون کسر هزینه ثبت شد.",B.now(),rid)
            )
        elif pid:
            # Already atomically deducted above.
            pass
        else:
            B.db.conn.execute(
                "UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='invoice',updated_at=? WHERE id=?",
                (B.now(),rid)
            )
        B.db.conn.commit()

        text_msg = _admin_text(st,code,amount,bool(previous),previous['tracking_code'] if previous else "")
        controls = _controls(rid)

        # Do not send an unpaid request to management. Customer evidence and
        # the receipt are forwarded together after receipt submission.
        if previous or pid:
            await B.notify_admins(context.application, text_msg, rid)
            for aid in B.ADM:
                if typ == "passport":
                    captions=["📸 ۱/۳ — صفحه اول پاسپورت","📸 ۲/۳ — صفحه تمدید روادید","📸 ۳/۳ — صفحه تمدید گذرنامه"]
                    for fid,caption in zip(attachments,captions):
                        try: await context.bot.send_photo(chat_id=int(aid),photo=fid,caption=f"🎫 {code}\\n{caption}")
                        except Exception:
                            try: await context.bot.send_document(chat_id=int(aid),document=fid,caption=f"🎫 {code}\\n{caption}")
                            except Exception: pass
                elif attachments:
                    fid=attachments[0]
                    try: await context.bot.send_photo(chat_id=int(aid),photo=fid,caption=f"🎫 {code}\\n📎 تصویر مدرک مشترک")
                    except Exception:
                        try: await context.bot.send_document(chat_id=int(aid),document=fid,caption=f"🎫 {code}\\n📎 تصویر مدرک مشترک")
                        except Exception: pass

        st["mode"] = None; st["request_id"] = rid; st["tracking_code"] = code
        if previous:
            await msg.reply_text(
                f"✅ درخواست جدید ثبت شد.\\n🎫 کد پیگیری: {code}\\n♻️ این شناسه اختصاصی قبلاً پرداخت شده است.\\n💰 هزینه این درخواست: ۰ تومان",
                reply_markup=B.partner_kb(st.get("lang","fa")) if pid else B.main(uid)
            )
        elif pid:
            await msg.reply_text(
                f"✅ درخواست با موفقیت ثبت شد.\\n🎫 کد پیگیری: {code}\\n💰 مبلغ {amount:,} تومان از اعتبار پنل همکاران کسر شد.",
                reply_markup=B.partner_kb(st.get("lang","fa"))
            )
        else:
            st["mode"] = "invoice_pending"
            await msg.reply_text(
                invoice_text("فاکتور خدمات حل مشکل سامانه دولت من",amount,code,B),
                reply_markup=invoice_markup(B),parse_mode="HTML"
            )
        raise ApplicationHandlerStop

    async def media(update, context):
        if not update.message: return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{}) ; mode=st.get("mode")
        if mode not in {"govv2_photo","govv2_passport_photo1","govv2_passport_photo2","govv2_passport_photo3"}: return
        fid=_file_id(update.message)
        if not fid:
            await update.message.reply_text("❌ لطفاً عکس یا فایل مدرک را ارسال کنید.",reply_markup=cancel); raise ApplicationHandlerStop
        if mode=="govv2_passport_photo1":
            st["gov_passport_photo1"]=fid; st["mode"]="govv2_passport_photo2"; await update.message.reply_text("📸 ۲/۳ — لطفاً عکس صفحه تمدید روادید را ارسال کنید:",reply_markup=cancel); raise ApplicationHandlerStop
        if mode=="govv2_passport_photo2":
            st["gov_passport_photo2"]=fid; st["mode"]="govv2_passport_photo3"; await update.message.reply_text("📸 ۳/۳ — لطفاً عکس تمدید گذرنامه را ارسال کنید:",reply_markup=cancel); raise ApplicationHandlerStop
        if mode=="govv2_passport_photo3":
            st["gov_passport_photo3"]=fid; await _create_request(update,context,st,[st.get("gov_passport_photo1"),st.get("gov_passport_photo2"),st.get("gov_passport_photo3")]); raise ApplicationHandlerStop
        await _create_request(update,context,st,[fid]); raise ApplicationHandlerStop

    async def receipt(update, context):
        if not update.message: return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        if st.get("mode") != "invoice_pending": return
        fid=_file_id(update.message)
        if not fid: return
        rid=st.get("request_id"); code=st.get("tracking_code","-")
        row=B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1",(int(rid),)).fetchone() if rid else None
        if not row:
            st["mode"]=None
            await update.message.reply_text("❌ فاکتور معتبر پیدا نشد.",reply_markup=B.main(uid))
            raise ApplicationHandlerStop
        B.db.answer(rid,"payment_receipt",file_id=fid)
        B.db.conn.execute(
            "UPDATE requests SET status='submitted',payment_status='pending_review',payment_method='card_to_card',updated_at=? WHERE id=?",
            (B.now(),int(rid))
        )
        B.db.conn.commit()
        try:
            await B.notify_admins(
                context.application,
                f"🧾 رسید پرداخت مشترک\\n🎫 {code}\\n💰 مبلغ: {int(row['amount'] or 0):,} تومان\\n"
                "💳 روش پرداخت: کارت‌به‌کارت\\n⏳ وضعیت: منتظر تأیید مدیریت",
                int(rid),
            )
        except Exception:
            log.exception("government receipt admin notification failed rid=%s",rid)
        st["mode"]=None
        await update.message.reply_text(
            "✅ رسید پرداخت برای مدیریت ارسال شد.\\n"
            "⏳ تا تأیید مدیریت، پرداخت قطعی محسوب نمی‌شود.",
            reply_markup=B.main(uid)
        )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-80)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,media),group=-80)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,receipt),group=-79)
    B._gov_runtime_fix=True