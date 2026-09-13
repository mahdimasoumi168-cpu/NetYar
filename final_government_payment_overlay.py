"""Final government payment/data correction loaded after all Telegram layers.
Temporary-card requests use family code, never temporary-card number. Partners
pay from balance; customers submit a card-to-card receipt. No /data mutation.
"""
import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters


def install(app, B):
    async def media(update, context):
        if not update.effective_message:
            return
        uid=update.effective_user.id
        st=B.S.setdefault(uid,{})
        if st.get("mode")!="govv2_photo":
            return
        msg=update.effective_message
        fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
        if not fid:
            return
        amount=int(B.db.setting("price_government","500000") or 500000)
        pid=st.get("partner_id")
        owner=pid or B.db.user("telegram",uid,update.effective_user.username,update.effective_user.full_name)
        rid,code=B.db.create_request(owner,"government","telegram",amount)
        typ=st.get("gov_doc_type")
        fields={"doc_type":typ,"phone":st.get("gov_phone"),"dob":st.get("gov_dob"),"unique_id":st.get("gov_unique"),"special_id":st.get("gov_special"),"postal_code":st.get("gov_postal")}
        if typ in {"card","temporary_card"}:
            fields["family_code"]=st.get("gov_family_code")
        elif typ=="passport":
            fields["passport"]=st.get("gov_identity_number")
        elif typ=="residence_booklet":
            fields["booklet_number"]=st.get("gov_identity_number")
        if pid:
            row=B.db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
            bal=int(row["balance"] or 0) if row else 0
            if not row or bal<amount:
                B.db.conn.execute("DELETE FROM requests WHERE id=?",(rid,));B.db.conn.commit()
                return await msg.reply_text(f"❌ اعتبار پنل همکاران کافی نیست.\n💳 اعتبار فعلی: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان\n\nابتدا حساب را از طریق کارت‌به‌کارت شارژ و تأیید مدیریت کنید.",reply_markup=B.partner_kb(st.get("lang","fa")))
            try:
                B.db.conn.execute("BEGIN IMMEDIATE")
                cur=B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?",(amount,B.now(),pid,amount))
                if cur.rowcount!=1: raise RuntimeError("insufficient balance")
                for k,v in fields.items():
                    if v:B.db.answer(rid,k,answer=str(v))
                B.db.answer(rid,"document",file_id=fid)
                B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid))
                B.db.conn.commit()
            except Exception:
                try:
                    B.db.conn.rollback()
                    B.db.conn.execute("DELETE FROM requests WHERE id=?",(rid,));B.db.conn.commit()
                except Exception: pass
                return await msg.reply_text("❌ ثبت خدمت انجام نشد؛ هیچ مبلغی از اعتبار کسر نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))
            text=f"🆕 درخواست دولت من — همکار\n🎫 {code}\n🪪 مدرک: {typ}\n📱 موبایل: {st.get('gov_phone','-')}\n🔖 شناسه فیدا: {st.get('gov_special','-')}\n"
            if typ in {"card","temporary_card"}: text+=f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family_code','-')}\n"
            text+=f"📮 کد پستی: {st.get('gov_postal','-')}\n💰 مبلغ: {amount:,} تومان\n💳 پرداخت: اعتبار پنل همکار"
            controls=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 جزئیات کامل",callback_data=f"req:v:{rid}")],[InlineKeyboardButton("⏳ بررسی",callback_data=f"req:review:{rid}"),InlineKeyboardButton("❌ رد",callback_data=f"req:x:{rid}")]])
            for aid in B.ADM:
                try:
                    if msg.photo: await context.bot.send_photo(int(aid),fid,caption=text,reply_markup=controls)
                    else: await context.bot.send_document(int(aid),fid,caption=text,reply_markup=controls)
                except Exception: pass
            st["mode"]=None
            return await msg.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💳 {amount:,} تومان از اعتبار پنل کسر شد.",reply_markup=B.partner_kb(st.get("lang","fa")))
        for k,v in fields.items():
            if v:B.db.answer(rid,k,answer=str(v))
        B.db.answer(rid,"document",file_id=fid)
        B.db.conn.execute("UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
        card=os.getenv("PAYMENT_CARD","") or B.db.setting("card_number","")
        owner_name=os.getenv("PAYMENT_CARD_OWNER","") or B.db.setting("card_owner","")
        st.update(mode="gov_customer_receipt",gov_request_id=rid,gov_tracking_code=code)
        return await msg.reply_text(f"🧾 فاکتور حل مشکل سامانه دولت من\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان\n💳 شماره کارت: {card or 'در تنظیمات ثبت نشده'}\n👤 به نام: {owner_name or '-'}\n\nپس از کارت‌به‌کارت، عکس رسید را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data="govv2:cancel")]]))

    async def receipt(update, context):
        if not update.effective_message:return
        uid=update.effective_user.id;st=B.S.setdefault(uid,{})
        if st.get("mode")!="gov_customer_receipt":return
        msg=update.effective_message;fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
        if not fid:return
        rid=st.get("gov_request_id");code=st.get("gov_tracking_code","-")
        B.db.answer(rid,"payment_receipt",file_id=fid);B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='pending_review',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
        for aid in B.ADM:
            try: await context.bot.send_photo(int(aid),fid,caption=f"🧾 رسید پرداخت دولت من\n🎫 {code}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"req:payconfirm:{rid}")],[InlineKeyboardButton("❌ رد درخواست",callback_data=f"req:x:{rid}")]]))
            except Exception: pass
        st["mode"]=None
        return await msg.reply_text("✅ رسید برای مدیریت ارسال شد. پس از تأیید، درخواست بررسی می‌شود.",reply_markup=B.main(uid))

    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media),group=-9500)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,receipt),group=-9499)
    B._final_government_payment_overlay=True
