import logging
log=logging.getLogger("netyar.gov")
def install():
 import bot as B
 if getattr(B,"_gov_postal_installed",False): return
 old_router=B.router; old_media=B.media
 async def router(u,c):
  uid=u.effective_user.id; st=B.S.setdefault(uid,{})
  t=(u.message.text or "").strip() if u.message else ""
  if st.get("mode")=="gov_postal":
   t=str(t).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")).replace(" ","").replace("-","")
   if not t.isdigit() or len(t)!=10:
    return await u.message.reply_text("❌ کد پستی صحیح نیست. کد پستی ۱۰ رقمی منزل را وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
   pid=st.get("partner_id")
   if not pid:return await u.message.reply_text("❌ این خدمت باید از پنل همکاران ثبت شود.",reply_markup=B.main(uid))
   amount=int(B.db.setting("price_government","500000") or 500000)
   p=B.db.conn.execute("SELECT * FROM partners WHERE id=?",(pid,)).fetchone()
   if not p:return await u.message.reply_text("❌ حساب همکار پیدا نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))
   bal=int(p["balance"] or 0)
   if bal<amount:return await u.message.reply_text(f"❌ اعتبار کافی نیست. هزینه: {amount:,} تومان | اعتبار: {bal:,} تومان",reply_markup=B.partner_kb(st.get("lang","fa")))
   rid,code=B.db.create_request(pid,"government","telegram",amount)
   vals=[("doc_type",st.get("gov_doc_type")),("phone",st.get("gov_phone")),("dob",st.get("dob")),("unique_id",st.get("gov_unique")),("special_id",st.get("gov_special")),("postal_code",t)]
   if st.get("gov_doc_type")=="passport": vals.append(("passport",st.get("gov_passport")))
   for k,v in vals:
    if v:B.db.answer(rid,k,answer=v)
   if st.get("gov_document"):B.db.answer(rid,"document",file_id=st["gov_document"])
   B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid))
   B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,B.now(),pid));B.db.conn.commit()
   left=bal-amount;st["mode"]=None
   msg=f"🆕 درخواست دولت من\n🎫 کد: {code}\n👥 همکار: {p['name']}\n📱 موبایل: {st.get('gov_phone','-')}\n🎂 تولد: {st.get('dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی: {st.get('gov_special','-')}\n📍 کد پستی منزل: {t}\n💰 کسر از اعتبار: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان"
   try: await B.notify_admins(c.application,msg,rid)
   except Exception: log.exception("admin notify")
   return await u.message.reply_text(f"✅ درخواست ثبت شد.\n🎫 {code}\n💰 کسر از اعتبار: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان",reply_markup=B.partner_kb(st.get("lang","fa")))
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
 log.info("Government postal final flow installed")
