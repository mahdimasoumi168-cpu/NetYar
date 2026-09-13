"""Deterministic Government flow runtime.

This is the single early handler for govv2 text/media states. Partner requests
are billed only from partner balance; customer requests use the shared manual
card-to-card invoice.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
from payment_invoice import invoice_text, invoice_markup


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def install(app, B):
    if getattr(B, "_gov_runtime_fix", False): return

    async def text(update, context):
        if not update.message: return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        mode=st.get("mode")
        if not str(mode or "").startswith("govv2_"): return
        t=(update.message.text or "").strip(); d=_digits(t)
        cancel=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data="govv2:cancel")]])
        if mode=="govv2_phone":
            p=re.sub(r"\D","",d)
            if p.startswith("98"): p="0"+p[2:]
            if not re.fullmatch(r"09\d{9}",p): await update.message.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.",reply_markup=cancel)
            else: st["gov_phone"]=p; st["mode"]="govv2_dob"; await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:",reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode=="govv2_dob":
            st["gov_dob"]=t; st["mode"]="govv2_unique"; await update.message.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:",reply_markup=cancel); raise ApplicationHandlerStop
        if mode=="govv2_unique":
            if len(t)<3: await update.message.reply_text("❌ شناسه یکتا را صحیح وارد کنید.",reply_markup=cancel)
            else: st["gov_unique"]=t; st["mode"]="govv2_special"; await update.message.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:",reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode=="govv2_special":
            if not re.fullmatch(r"1\d{11}",d): await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.",reply_markup=cancel)
            else:
                st["gov_special"]=d; typ=st.get("gov_doc_type")
                if typ=="card": st["mode"]="govv2_family"; await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (فقط برای کارت آمایش):",reply_markup=cancel)
                else:
                    st["mode"]="govv2_identity_number"
                    prompt="🛂 شماره گذرنامه مشترک را وارد کنید:" if typ=="passport" else "📗 شماره دفترچه اقامت مشترک را وارد کنید:" if typ=="residence_booklet" else "🪪 شماره کارت موقت مشترک را وارد کنید:"
                    await update.message.reply_text(prompt,reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode=="govv2_family":
            if not d.isdigit(): await update.message.reply_text("❌ کد خانوار باید عددی باشد.",reply_markup=cancel)
            else: st["gov_family_code"]=d; st["mode"]="govv2_postal"; await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode=="govv2_identity_number":
            if len(t)<3: await update.message.reply_text("❌ شماره مدرک را صحیح وارد کنید.",reply_markup=cancel)
            else: st["gov_identity_number"]=t; st["mode"]="govv2_postal"; await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel)
            raise ApplicationHandlerStop
        if mode=="govv2_postal":
            if not re.fullmatch(r"\d{10}",d): await update.message.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.",reply_markup=cancel)
            else: st["gov_postal"]=d; st["mode"]="govv2_photo"; await update.message.reply_text("📸 حالا تصویر مدرک مشترک را ارسال کنید:",reply_markup=cancel)
            raise ApplicationHandlerStop

    async def media(update, context):
        if not update.message: return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        if st.get("mode")!="govv2_photo": return
        msg=update.message; fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
        if not fid: return
        amount=int(B.db.setting("price_government","500000") or 500000); pid=st.get("partner_id")
        partner=None
        if pid:
            partner=B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
            if not partner or int(partner["balance"] or 0)<amount:
                bal=int(partner["balance"] or 0) if partner else 0
                await msg.reply_text(f"❌ اعتبار همکار کافی نیست.\n💰 هزینه خدمت: {amount:,} تومان\n💳 اعتبار فعلی: {bal:,} تومان\n\nلطفاً ابتدا «➕ شارژ حساب» را انجام دهید.",reply_markup=B.partner_kb(st.get("lang","fa")))
                raise ApplicationHandlerStop
        owner=pid or B.db.user("telegram",uid,update.effective_user.username,update.effective_user.full_name)
        rid,code=B.db.create_request(owner,"government","telegram",amount)
        fields=[("doc_type",st.get("gov_doc_type")),("phone",st.get("gov_phone")),("dob",st.get("gov_dob")),("unique_id",st.get("gov_unique")),("special_id",st.get("gov_special")),("postal_code",st.get("gov_postal"))]
        typ=st.get("gov_doc_type")
        if typ=="card": fields.append(("family_code",st.get("gov_family_code")))
        if typ=="passport": fields.append(("passport",st.get("gov_identity_number")))
        if typ=="temporary_card": fields.append(("temporary_card_number",st.get("gov_identity_number")))
        if typ=="residence_booklet": fields.append(("booklet_number",st.get("gov_identity_number")))
        if pid: fields.append(("partner_id",str(pid)))
        for k,v in fields:
            if v: B.db.answer(rid,k,answer=v)
        B.db.answer(rid,"document",file_id=fid)

        if pid:
            B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid))
            B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),pid)); B.db.conn.commit()
        else:
            B.db.conn.execute("UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()

        typ_name={"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}.get(typ,"-")
        text=(f"👔 مدیر — درخواست جدید\n🆕 حل مشکل سامانه دولت من\n🎫 {code}\n🪪 مدرک: {typ_name}\n📱 موبایل مشترک: {st.get('gov_phone','-')}\n🎂 تاریخ تولد: {st.get('gov_dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی: {st.get('gov_special','-')}\n"+(f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family_code','-')}\n" if typ=="card" else "")+(f"🛂 شماره پاسپورت: {st.get('gov_identity_number','-')}\n" if typ=="passport" else f"📗 شماره دفترچه اقامت: {st.get('gov_identity_number','-')}\n" if typ=="residence_booklet" else f"🪪 شماره کارت موقت: {st.get('gov_identity_number','-')}\n" if typ=="temporary_card" else "")+f"📮 کد پستی: {st.get('gov_postal','-')}\n💰 مبلغ: {amount:,} تومان\n"+(f"💳 پرداخت: از اعتبار همکار\n💵 اعتبار باقی‌مانده: {int(partner['balance'])-amount:,} تومان\n" if pid else "💳 پرداخت: کارت به کارت؛ در انتظار تأیید مدیریت\n"))
        controls=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 جزئیات کامل",callback_data=f"rq:detail:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"panel:askcode:{rid}")],[InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")]] + ([] if pid else [[InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"rq:payconfirm:{rid}")]]))
        for aid in B.ADM:
            try:
                if msg.photo: await context.bot.send_photo(int(aid),fid,caption=text,reply_markup=controls)
                else: await context.bot.send_document(int(aid),fid,caption=text,reply_markup=controls)
            except Exception: pass
        st["mode"]="invoice_pending" if not pid else None; st["request_id"]=rid; st["tracking_code"]=code
        if pid:
            left=int(partner["balance"])-amount
            await msg.reply_text(f"✅ درخواست با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n💰 هزینه: {amount:,} تومان\n💳 از اعتبار همکار کسر شد.\n💵 اعتبار باقی‌مانده: {left:,} تومان",reply_markup=B.partner_kb(st.get("lang","fa")))
        else:
            await msg.reply_text(invoice_text("فاکتور خدمات حل مشکل سامانه دولت من",amount,code,B),reply_markup=invoice_markup(B),parse_mode="HTML")
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-80)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,media),group=-80)
    B._gov_runtime_fix=True
