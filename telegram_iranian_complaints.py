"""Iranian subscriber UX + complaint/contact handling."""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters
log=logging.getLogger("netyar.telegram.iranian")
CONTACT_USERNAME="Good_ok_2000"

def _menu():
 return InlineKeyboardMarkup([[InlineKeyboardButton("🏛 حل مشکل ورود اتباع دولت من",callback_data="ir:gov")],[InlineKeyboardButton("🎫 پیگیری",callback_data="ir:track"),InlineKeyboardButton("💰 کیف پول من",callback_data="ir:wallet")],[InlineKeyboardButton("📞 تماس با ما",url="https://t.me/Good_ok_2000"),InlineKeyboardButton("📝 ثبت شکایت",callback_data="ir:complaint")],[InlineKeyboardButton("🔵 👥 پنل همکاران",callback_data="ir:partner")],[InlineKeyboardButton("🔄 شروع مجدد",callback_data="ir:restart")]])

def install(app,B):
 if getattr(B,"_iranian_complaints_installed",False):return
 old_status=B.statuscb
 async def status(update,context):
  q=update.callback_query
  if q.data!="st:iranian":return await old_status(update,context)
  await q.answer();st=B.S.setdefault(q.from_user.id,{});st.update({"status":"iranian"});st.pop("mode",None)
  return await q.message.reply_text("🇮🇷 منوی مشترکین ایرانی\n\nخدمات عادی برای مشترکین ایرانی غیرفعال است. گزینه فعال موردنظر را انتخاب کنید:",reply_markup=_menu())
 async def cb(update,context):
  q=update.callback_query;a=q.data or ""
  if not a.startswith("ir:"):return
  await q.answer();st=B.S.setdefault(q.from_user.id,{});act=a.split(":",1)[1]
  if act=="gov":st["mode"]="gov_doc_type";return await q.message.reply_text("🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=B.kb([["🪪 کارت آمایش","🛂 گذرنامه"],["📗 دفترچه اقامت"],[B.CANCEL]]))
  if act=="track":st["mode"]="track";return await q.message.reply_text("🎫 کد پیگیری را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
  if act=="wallet":
   try:return await B.customer_wallet(update,context)
   except Exception:return await q.message.reply_text("💰 کیف پول من\n\nموجودی کیف پول شما در دسترس است.",reply_markup=_menu())
  if act=="partner":st["mode"]="p_phone";return await q.message.reply_text("📱 شماره همراه همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
  if act=="complaint":st["mode"]="iranian_complaint";return await q.message.reply_text("📝 ثبت شکایت\n\nمتن شکایت یا انتقاد خود را ارسال کنید.")
  if act=="restart":st.clear();st["lang"]="fa";return await B.start(update,context)
 async def text(update,context):
  uid=update.effective_user.id;st=B.S.setdefault(uid,{})
  if st.get("mode")=="iranian_complaint":
   t=(update.message.text or "").strip();u=update.effective_user
   if not t:return await update.message.reply_text("❌ متن شکایت خالی است.")
   un=f"@{u.username}" if u.username else "ندارد";msg=f"📝 شکایت/انتقاد جدید\n\n👤 نام: {u.full_name or '-'}\n🔹 آیدی عددی: {u.id}\n🔹 یوزرنیم: {un}\n\n💬 متن شکایت:\n{t}"
   try:await B.notify_admins(context.application,msg)
   except Exception:log.exception("complaint notification failed")
   st["mode"]=None;return await update.message.reply_text("✅ شکایت شما برای مدیریت ارسال شد.",reply_markup=_menu())
  return await B.ptext(update,context)
 app.add_handler(CallbackQueryHandler(status,pattern=r"^st:iranian$"),group=-10);app.add_handler(CallbackQueryHandler(cb,pattern=r"^ir:"),group=-9);app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-10);B._iranian_complaints_installed=True
