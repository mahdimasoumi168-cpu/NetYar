"""Iranian subscriber UX + complaint/contact handling.

Iranian subscribers only get the enabled customer actions: government-login
help, tracking, wallet, contact, complaint, and partner panel. Other customer
services are intentionally hidden/disabled from this menu.
"""
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger("netyar.telegram.iranian")

CONTACT_USERNAME = os.getenv("CONTACT_USERNAME", "").strip().lstrip("@")


def _menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛 حل مشکل ورود اتباع دولت من", callback_data="ir:gov")],
        [InlineKeyboardButton("🎫 پیگیری", callback_data="ir:track"), InlineKeyboardButton("💰 کیف پول من", callback_data="ir:wallet")],
        [InlineKeyboardButton("📞 تماس با ما", callback_data="ir:contact"), InlineKeyboardButton("📝 ثبت شکایت", callback_data="ir:complaint")],
        [InlineKeyboardButton("🔵 👥 پنل همکاران", callback_data="ir:partner")],
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="ir:restart")],
    ])


def install(app, B):
    if getattr(B, "_iranian_complaints_installed", False):
        return

    old_status = B.statuscb
    async def status(update, context):
        q = update.callback_query
        if q.data != "st:iranian":
            return await old_status(update, context)
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        st.update({"status": "iranian"})
        st.pop("mode", None)
        return await q.message.reply_text("🇮🇷 منوی مشترکین ایرانی\n\nخدمات عادی برای مشترکین ایرانی غیرفعال است. گزینه فعال موردنظر را انتخاب کنید:", reply_markup=_menu())

    async def callback(update, context):
        q = update.callback_query
        data = q.data or ""
        if not data.startswith("ir:"):
            return
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        action = data.split(":", 1)[1]
        if action == "gov":
            st["status"] = "iranian"
            return await B.gov(update, context) if False else await q.message.reply_text("🏛 حل مشکل ورود اتباع دولت من\n\nاین خدمت برای ثبت درخواست فعال است. برای شروع، نوع مدرک را انتخاب کنید:", reply_markup=B.kb([["🪪 کارت آمایش", "🛂 گذرنامه"], ["📗 دفترچه اقامت"], [B.CANCEL]]))
        if action == "track":
            st["mode"] = "track"
            return await q.message.reply_text("🎫 کد پیگیری را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if action == "wallet":
            try:
                return await B.customer_wallet(update, context)
            except Exception:
                return await q.message.reply_text("💰 کیف پول من\n\nدر حال حاضر موجودی کیف پول شما از این بخش قابل مشاهده است.")
        if action == "partner":
            try:
                return await B.partner_login(update, context)
            except Exception:
                st["mode"] = "p_phone"
                return await q.message.reply_text("📱 شماره همراه همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if action == "contact":
            if CONTACT_USERNAME:
                return await q.message.reply_text("📞 تماس با ما\n\nبرای ارتباط مستقیم روی دکمه زیر بزنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 ارتباط با پشتیبانی", url=f"https://t.me/{CONTACT_USERNAME}")], [InlineKeyboardButton("⬅️ بازگشت", callback_data="ir:back")]]))
            return await q.message.reply_text("📞 آیدی تماس با ما هنوز در تنظیمات ربات ثبت نشده است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="ir:back")]]))
        if action == "complaint":
            st["mode"] = "iranian_complaint"
            return await q.message.reply_text("📝 ثبت شکایت\n\nلطفاً متن شکایت یا انتقاد خود را کامل بنویسید.\nپس از ارسال، متن همراه با مشخصات کاربری شما برای مدیریت ارسال می‌شود.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if action == "back":
            st["mode"] = None
            return await q.message.reply_text("🇮🇷 منوی مشترکین ایرانی:", reply_markup=_menu())
        if action == "restart":
            st.clear(); st["lang"] = "fa"
            return await B.start(update, context)

    async def complaint_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "iranian_complaint":
            return
        text = (update.message.text or "").strip()
        if not text:
            return await update.message.reply_text("❌ متن شکایت خالی است. لطفاً توضیح خود را بنویسید.")
        user = update.effective_user
        username = f"@{user.username}" if user.username else "ندارد"
        message = (
            "📝 شکایت/انتقاد جدید از ربات\n\n"
            f"👤 نام: {user.full_name or '-'}\n"
            f"🔹 آیدی عددی: {user.id}\n"
            f"🔹 یوزرنیم: {username}\n\n"
            f"💬 متن شکایت:\n{text}"
        )
        try:
            await B.notify_admins(context.application, message)
        except Exception:
            log.exception("complaint notification failed")
            return await update.message.reply_text("❌ ارسال شکایت ناموفق بود. لطفاً دوباره تلاش کنید.")
        st["mode"] = None
        return await update.message.reply_text("✅ شکایت شما با موفقیت برای مدیریت ارسال شد.", reply_markup=_menu())

    async def track_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "track" or st.get("status") != "iranian":
            return
        # Let the canonical tracking implementation handle the code. We only
        # route the Iranian subscriber into the same existing flow.
        return await B.ptext(update, context)

    app.add_handler(CallbackQueryHandler(status, pattern=r"^st:iranian$"), group=-10)
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ir:"), group=-9)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_text), group=-10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_text), group=-9)
    B._iranian_complaints_installed = True
