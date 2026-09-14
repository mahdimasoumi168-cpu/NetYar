"""Safe business-flow fixes layered on top of the existing runtime."""
import logging,re
log=logging.getLogger("netyar.business_flow_patch")
def _amount(text):
 s=str(text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"));s=s.replace(",","").replace("٬","").replace("تومان","").replace(" ","");return int(s) if s.isdigit() and int(s)>0 else None

def install():
 import bot as B
 from telegram import InlineKeyboardMarkup,InlineKeyboardButton
 if getattr(B,"_business_flow_patch_installed",False):return
 old_main=B.main
 def main(uid):
  markup=old_main(uid);st=B.S.get(uid,{})
  if st.get("status")!="iranian":return markup
  return B.kb([["🎫 پیگیری","👥 پنل همکاران"],["💰 اعتبار من","⬅️ بازگشت"],["📞 تماس با ما","📝 ثبت شکایت مشتریان"],[B.CANCEL]])
 B.main=main
 old_service_text=B.service_text
 async def service_text(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{});t=(update.message.text or "").strip()
  if st.get("mode")=="topup_amount":
   amount=_amount(t)
   if not amount:return await update.message.reply_text("❌ مبلغ نامعتبر است. فقط عدد وارد کنید؛ مثال: 500000",reply_markup=B.cancel_kb(st.get("lang","fa")))
   pid=st.get("partner_id");p=B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
   if not p:st["mode"]=None;return await update.message.reply_text("❌ حساب همکار پیدا نشد.",reply_markup=B.main(uid))
   st["topup_amount"]=amount;st["mode"]="topup_receipt"
   return await update.message.reply_text(f"💰 مبلغ شارژ: {amount:,} تومان\n\n📎 حالا تصویر یا فایل رسید واریز را ارسال کنید.\n\nبعد از ارسال رسید، درخواست برای مدیریت فرستاده می‌شود.",reply_markup=B.cancel_kb(st.get("lang","fa")))
  return await old_service_text(update,context)
 B.service_text=service_text
 old_media=B.media
 async def media(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{})
  if st.get("mode")=="topup_receipt":
   msg=update.message;fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
   if not fid:return await msg.reply_text("❌ لطفاً تصویر یا فایل رسید را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
   pid=st.get("partner_id");amount=int(st.get("topup_amount") or 0);p=B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
   if not p or amount<=0:st["mode"]=None;st.pop("topup_amount",None);return await msg.reply_text("❌ درخواست شارژ پیدا نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))
   cur=B.db.conn.execute("INSERT INTO topups(partner_id,amount,receipt_file_id,status,created_at) VALUES(?,?,?,?,?)",(pid,amount,fid,"pending",B.now()));topup_id=cur.lastrowid;B.db.conn.commit();st["mode"]=None;st.pop("topup_amount",None)
   mk=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید شارژ",callback_data=f"tu:a:{pid}:{amount}:{topup_id}"),InlineKeyboardButton("❌ رد شارژ",callback_data=f"tu:r:{pid}:{amount}:{topup_id}")]])
   text=f"💰 درخواست شارژ حساب\n👤 {p['name']}\n📱 {p['phone']}\n💵 مبلغ: {amount:,} تومان\n🎫 شناسه شارژ: {topup_id}\n📎 رسید پیوست شده است."
   for aid in B.ADM:
    try:
     await context.bot.send_message(chat_id=int(aid),text=text,reply_markup=mk)
     if msg.photo:await context.bot.send_photo(chat_id=int(aid),photo=fid,caption=f"📎 رسید شارژ {topup_id}")
     elif msg.document:await context.bot.send_document(chat_id=int(aid),document=fid,caption=f"📎 رسید شارژ {topup_id}")
    except Exception:log.exception("topup admin notification failed")
   return await msg.reply_text("✅ رسید دریافت شد و همراه با درخواست شارژ برای مدیریت ارسال شد. پس از تأیید، موجودی شما افزایش می‌یابد.",reply_markup=B.partner_kb(st.get("lang","fa")))
  return await old_media(update,context)
 B.media=media
 old_router=B.router
 async def router(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{});t=(update.message.text or "").strip()
  if t in ("💰 اعتبار من","💰 کیف پول من","💰 My wallet","💰 محفظتي") and not B.admin(uid):
   return await B.customer_wallet(update,context)
  if t=="⬅️ بازگشت" and st.get("status")=="iranian":
   st["status"]=None
   return await update.message.reply_text("لطفاً انتخاب کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم",callback_data="st:foreign"),InlineKeyboardButton("🇮🇷 ایرانی هستم",callback_data="st:iranian")]]))
  return await old_router(update,context)
 B.router=router;B._business_flow_patch_installed=True
 log.info("business flow patch installed")
