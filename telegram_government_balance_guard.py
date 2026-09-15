import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def _d(v):
    return str(v or "").translate(DIGITS).strip()

def _fid(msg):
    if getattr(msg, "photo", None): return msg.photo[-1].file_id
    if getattr(msg, "document", None): return msg.document.file_id
    return ""

def _cancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]])

def _sim_choice():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 ارسال سند سیم‌کارت", callback_data="govv2:sim_document")],
        [InlineKeyboardButton("⏭ بدون سند سیم‌کارت", callback_data="govv2:sim_skip")],
        [InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")],
    ])

def install(app, B):
    if getattr(B, "_gov_balance_guard", False): return

    async def cb(update, context):
        q = update.callback_query
        if not q: return
        data = str(q.data or "")
        if data == "govv2:sim_document":
            await q.answer(); st=B.S.setdefault(q.from_user.id,{})
            if not str(st.get("mode","")).startswith("govv2_"): return
            st["mode"]="govv2_sim_document"
            await q.message.reply_text("📎 لطفاً سند سیم‌کارت مشترک را ارسال کنید.\nاین مرحله اختیاری است.", reply_markup=_cancel())
            raise ApplicationHandlerStop
        if data == "govv2:sim_skip":
            await q.answer(); st=B.S.setdefault(q.from_user.id,{})
            if not str(st.get("mode","")).startswith("govv2_"): return
            st["gov_sim_document"]=""
            await _submit(update, context, st, B, q.message)
            raise ApplicationHandlerStop

    async def text(update, context):
        if not update.message: return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        mode=st.get("mode"); t=(update.message.text or "").strip(); d=_d(t)
        if mode == "govv2_special":
            if not re.fullmatch(r"1\d{11}", d):
                await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.",reply_markup=_cancel())
            else:
                st["gov_special"]=d
                if st.get("gov_doc_type") in ("card","temporary_card"):
                    st["mode"]="govv2_family"
                    await update.message.reply_text("👨‍👩‍👧‍👦 شناسه خانوار مشترک را وارد کنید:",reply_markup=_cancel())
                elif st.get("gov_doc_type")=="passport":
                    st["mode"]="govv2_identity_number"; await update.message.reply_text("🛂 شماره گذرنامه مشترک را وارد کنید:",reply_markup=_cancel())
                else:
                    st["mode"]="govv2_identity_number"; await update.message.reply_text("📗 شماره دفترچه اقامت مشترک را وارد کنید:",reply_markup=_cancel())
            raise ApplicationHandlerStop
        if mode == "govv2_family":
            if not d.isdigit(): await update.message.reply_text("❌ شناسه خانوار باید عددی باشد.",reply_markup=_cancel())
            else:
                st["gov_family_code"]=d;st["mode"]="govv2_postal"
                await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=_cancel())
            raise ApplicationHandlerStop
        if mode == "govv2_sim_document":
            return

    async def media(update, context):
        if not update.message: return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{}) ; mode=st.get("mode")
        if mode == "govv2_sim_document":
            fid=_fid(update.message)
            if not fid:
                await update.message.reply_text("❌ سند سیم‌کارت دریافت نشد.",reply_markup=_cancel()); raise ApplicationHandlerStop
            st["gov_sim_document"]=fid
            await _submit(update, context, st, B, update.message)
            raise ApplicationHandlerStop
        if mode == "govv2_photo":
            fid=_fid(update.message)
            if not fid: return
            st["gov_document"]=fid
            st["mode"]="govv2_sim_choice"
            await update.message.reply_text("📱 سند سیم‌کارت مشترک را دارید؟\nاین مرحله اختیاری است.",reply_markup=_sim_choice())
            raise ApplicationHandlerStop
        if mode == "govv2_passport_photo3":
            fid=_fid(update.message)
            if not fid: return
            st["gov_passport_photo3"]=fid
            st["mode"]="govv2_sim_choice"
            await update.message.reply_text("📱 سند سیم‌کارت مشترک را دارید؟\nاین مرحله اختیاری است.",reply_markup=_sim_choice())
            raise ApplicationHandlerStop

    async def _submit(update, context, st, B, msg):
        uid=update.effective_user.id; pid=st.get("partner_id")
        if not pid:
            await msg.reply_text("❌ این خدمت فقط از پنل همکاران قابل ثبت است.",reply_markup=B.main(uid)); return
        amount=int(B.db.setting("price_government","500000") or 500000)
        p=B.db.conn.execute("SELECT id,name,balance,active FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
        bal=int(p["balance"] or 0) if p else 0
        if not p or bal < amount:
            need=amount-bal
            await msg.reply_text(f"❌ موجودی کافی نیست.\n\n💳 موجودی فعلی: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان\n➕ مبلغ موردنیاز برای شارژ: {need:,} تومان\n\nابتدا حساب را شارژ کنید؛ تا شارژ انجام نشود درخواست خدمت برای مدیریت ارسال نمی‌شود.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ شارژ حساب",callback_data="topupui:start")],[InlineKeyboardButton("❌ انصراف",callback_data="govv2:cancel")]]))
            return
        try:
            conn=B.db.conn; conn.execute("BEGIN IMMEDIATE")
            row=conn.execute("SELECT balance FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
            if not row or int(row["balance"] or 0)<amount:
                conn.rollback(); await msg.reply_text("❌ موجودی در همین لحظه کافی نیست. ابتدا حساب را شارژ کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ شارژ حساب",callback_data="topupui:start")]])); return
            owner=pid
            rid,code=B.db.create_request(owner,"government","telegram",amount)
            typ=st.get("gov_doc_type")
            vals=[("doc_type",typ),("phone",st.get("gov_phone")),("dob",st.get("gov_dob")),("unique_id",st.get("gov_unique")),("special_id",st.get("gov_special")),("postal_code",st.get("gov_postal")),("partner_id",str(pid))]
            if typ in ("card","temporary_card"): vals.append(("family_code",st.get("gov_family_code")))
            elif typ=="passport": vals.append(("passport",st.get("gov_identity_number")))
            elif typ=="residence_booklet": vals.append(("booklet_number",st.get("gov_identity_number")))
            for k,v in vals:
                if v is not None and v!="": B.db.answer(rid,k,answer=str(v))
            attachments=[]
            if typ=="passport":
                for key in ("gov_passport_photo1","gov_passport_photo2","gov_passport_photo3"):
                    fid=st.get(key)
                    if fid: B.db.answer(rid,key.replace("gov_", ""),file_id=fid); attachments.append(fid)
            elif st.get("gov_document"):
                B.db.answer(rid,"document",file_id=st["gov_document"]); attachments.append(st["gov_document"])
            if st.get("gov_sim_document"):
                B.db.answer(rid,"sim_document",file_id=st["gov_sim_document"]); attachments.append(st["gov_sim_document"])
            conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid))
            conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),pid)); conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass
            raise
        typname={"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}.get(typ,"-")
        notice=(f"🆕 درخواست خدمت دولت من\n🎫 کد پیگیری: {code}\n👤 همکار: {p['name']}\n🪪 نوع مدرک: {typname}\n📱 موبایل مشترک: {st.get('gov_phone','-')}\n🎂 تاریخ تولد: {st.get('gov_dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی: {st.get('gov_special','-')}\n" + (f"👨‍👩‍👧‍👦 شناسه خانوار: {st.get('gov_family_code','-')}\n" if typ in ("card","temporary_card") else f"🛂 شماره گذرنامه: {st.get('gov_identity_number','-')}\n" if typ=="passport" else f"📗 شماره دفترچه اقامت: {st.get('gov_identity_number','-')}\n") + f"📮 کد پستی: {st.get('gov_postal','-')}\n💰 مبلغ پرداخت‌شده از شارژ: {amount:,} تومان\n💳 روش پرداخت: موجودی پنل همکاران\n📎 سند سیم‌کارت: {'ارسال شده' if st.get('gov_sim_document') else 'ندارد'}")
        await B.notify_admins(context.application,notice,rid)
        st["mode"]=None;st["request_id"]=rid;st["tracking_code"]=code
        await msg.reply_text(f"✅ خدمت با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ {amount:,} تومان از موجودی شارژ کسر شد.",reply_markup=B.partner_kb(st.get("lang","fa")))

    app.add_handler(CallbackQueryHandler(cb,pattern=r"^govv2:(sim_document|sim_skip)$"),group=-95)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media),group=-95)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-95)
    B._gov_balance_guard=True
