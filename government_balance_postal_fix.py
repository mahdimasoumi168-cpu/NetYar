import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
log=logging.getLogger("netyar.gov")

def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")).strip().replace(" ","").replace("-","")

def install():
    import bot as B
    if getattr(B,"_gov_postal_installed",False): return
    old_router=B.router; old_media=B.media
    async def router(u,c):
        uid=u.effective_user.id; st=B.S.setdefault(uid,{})
        t=(u.message.text or "").strip() if u.message else ""
        if st.get("mode")=="gov_postal":
            t=_digits(t)
            if not t.isdigit() or len(t)!=10:
                return await u.message.reply_text("❌ کد پستی صحیح نیست. کد پستی ۱۰ رقمی منزل را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
            pid=st.get("partner_id")
            if not pid:
                return await u.message.reply_text("❌ این خدمت باید از پنل همکاران ثبت شود.",reply_markup=B.main(uid))
            amount=int(B.db.setting("price_government","500000") or 500000)
            p=B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
            if not p:
                return await u.message.reply_text("❌ حساب همکار پیدا نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))

            # شناسه‌هایی که برای یک شخص می‌توانند پرداخت قبلی را مشخص کنند.
            unique_id=_digits(st.get("gov_unique"))
            special_id=_digits(st.get("gov_special"))
            fida_id=_digits(st.get("gov_fida") or st.get("fida_id") or st.get("fida"))
            previous=None
            identifiers=[("unique_id",unique_id,"شناسه یکتا"),("special_id",special_id,"شناسه اختصاصی"),("fida_id",fida_id,"شناسه فیدا")]
            for field,value,label in identifiers:
                if not value: continue
                previous=B.db.conn.execute(
                    """SELECT r.id,r.tracking_code,r.status,r.amount,a.field_key
                       FROM requests r JOIN request_answers a ON a.request_id=r.id
                       WHERE r.user_id=? AND r.service_key='government' AND r.payment_status='paid'
                         AND a.field_key=? AND a.answer=?
                       ORDER BY r.id DESC LIMIT 1""",
                    (pid,field,value),
                ).fetchone()
                if previous:
                    previous_label=label; previous_value=value; break
            else:
                previous_label=previous_value=""

            bal=int(p["balance"] or 0)
            if not previous and bal<amount:
                mk=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 شارژ حساب",callback_data="topupui:start")],
                    [InlineKeyboardButton("❌ انصراف",callback_data="cancel")],
                ])
                return await u.message.reply_text(
                    f"❌ اعتبار پنل همکاران کافی نیست.\n\n💳 اعتبار فعلی: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان\n\nبرای ادامه ابتدا حساب خود را شارژ کنید.",
                    reply_markup=mk,
                )

            rid,code=B.db.create_request(pid,"government","telegram",amount)
            vals=[("doc_type",st.get("gov_doc_type")),("phone",st.get("gov_phone")),("dob",st.get("dob")),
                  ("unique_id",unique_id),("special_id",special_id),("fida_id",fida_id),("postal_code",t)]
            if st.get("gov_doc_type")=="passport": vals.append(("passport",st.get("gov_passport")))
            for k,v in vals:
                if v:B.db.answer(rid,k,answer=v)
            if st.get("gov_document"):B.db.answer(rid,"document",file_id=st["gov_document"])

            if previous:
                B.db.conn.execute(
                    """UPDATE requests SET status='submitted',payment_status='paid',
                       payment_method='previous_government_request',payment_note=?,updated_at=? WHERE id=?""",
                    (f"هزینه قبلاً برای {previous_label} {previous_value} در درخواست {previous['tracking_code']} پرداخت شده است؛ درخواست مجدد بدون کسر موجودی ثبت شد.",B.now(),rid),
                )
                charged=0; left=bal
            else:
                B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid))
                B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),pid))
                charged=amount; left=bal-amount
            B.db.conn.commit()
            st["mode"]=None
            reuse_note=(f"\n♻️ {previous_label} قبلاً پرداخت شده است.\n💰 کسر این درخواست: ۰ تومان\n📌 درخواست قبلی: {previous['tracking_code']}" if previous else f"\n💰 کسر از اعتبار: {amount:,} تومان")
            msg=(f"🆕 درخواست دولت من\n🎫 کد: {code}\n👥 همکار: {p['name']}\n📱 موبایل: {st.get('gov_phone','-')}\n"
                 f"🎂 تولد: {st.get('dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique','-')}\n"
                 f"🔖 شناسه اختصاصی: {st.get('gov_special','-')}\n🪪 شناسه فیدا: {st.get('gov_fida','-')}\n"
                 f"📍 کد پستی منزل: {t}\n💰 کسر از اعتبار: {charged:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان" +
                 (f"\n♻️ پرداخت قبلی: {previous['tracking_code']} ({previous_label})" if previous else ""))
            try: await B.notify_admins(c.application,msg,rid)
            except Exception: log.exception("admin notify")
            return await u.message.reply_text(
                f"✅ درخواست ثبت شد.\n🎫 {code}"+reuse_note+f"\n💳 اعتبار باقی‌مانده: {left:,} تومان",
                reply_markup=B.partner_kb(st.get("lang","fa")))
        return await old_router(u,c)

    async def media(u,c):
        st=B.S.setdefault(u.effective_user.id,{})
        if st.get("mode")=="gov_photo":
            fid=u.message.photo[-1].file_id if u.message.photo else (u.message.document.file_id if u.message.document else "")
            if not fid:return await u.message.reply_text("❌ عکس یا فایل مدرک دریافت نشد.",reply_markup=B.cancel_kb(st.get("lang","fa")))
            st["gov_document"]=fid;st["mode"]="gov_postal"
            return await u.message.reply_text("📍 کد پستی منزل مشترک را وارد کنید.\nلطفاً کد پستی ۱۰ رقمی را بدون فاصله ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
        return await old_media(u,c)
    B.router=router;B.media=media;B._gov_postal_installed=True
    log.info("Government repeat-billing and balance redirect layer installed")
