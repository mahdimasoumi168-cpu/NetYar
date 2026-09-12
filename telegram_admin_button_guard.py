"""Terminal Telegram guard for admin entry and partner ticket entry."""
from telegram.ext import ApplicationHandlerStop, MessageHandler, filters

ADMIN_LABELS = {
    "🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "🔵 🛠 پنل مدیریت بات",
    "🔵 🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت",
    "🛠 Admin panel", "🛠 لوحة الإدارة",
}
PARTNER_TICKET_LABELS = {
    "✉️ ارسال تیکت به مدیریت", "📝 تیکت به مدیریت",
    "✉️ Ticket to management", "📝 Ticket to management",
    "✉️ إرسال تذكرة إلى الإدارة",
}
CANCEL_LABELS = {"❌ انصراف", "❌ Cancel", "❌ إلغاء", "لغو"}


async def _handle(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    text = str(message.text or "").strip()
    st = B.S.setdefault(user.id, {})

    # Terminal admin entry. ApplicationHandlerStop prevents older text routers
    # from treating the admin button as a normal service/menu command.
    if B.admin(user.id) and text in ADMIN_LABELS:
        st["admin"] = True
        st["mode"] = None
        st["admin_mode"] = None
        await message.reply_text(
            "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
            reply_markup=B.amenu(),
        )
        raise ApplicationHandlerStop

    # Terminal partner-ticket entry. This bypasses legacy routers that were
    # swallowing the ticket button after a menu replacement.
    if st.get("partner_id") and text in PARTNER_TICKET_LABELS:
        st["mode"] = "partner_ticket_text"
        await message.reply_text(
            "✉️ متن تیکت خود را ارسال کنید.\n\nبرای لغو، دکمه «انصراف» را بزنید.",
            reply_markup=B.kb([[B.CANCEL]]),
        )
        raise ApplicationHandlerStop

    # Handle the next partner-ticket message here as well, so it cannot fall
    # through to service handlers. Text is forwarded to every configured admin.
    if st.get("partner_id") and st.get("mode") == "partner_ticket_text":
        if text in CANCEL_LABELS:
            st["mode"] = None
            await message.reply_text("❌ عملیات لغو شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop
        if not text:
            return
        try:
            pid = st.get("partner_id")
            phone = st.get("phone", "-")
            payload = f"✉️ تیکت جدید همکار\n\n👤 شناسه همکار: {pid}\n📱 شماره: {phone}\n\n📝 متن:\n{text}"
            await B.notify_admins(context.application, payload)
            st["mode"] = None
            await message.reply_text(
                "✅ تیکت شما برای مدیریت ارسال شد.",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )
        except Exception:
            await message.reply_text(
                "❌ ارسال تیکت ناموفق بود. لطفاً دوباره تلاش کنید.",
                reply_markup=B.kb([[B.CANCEL]]),
            )
        raise ApplicationHandlerStop


def install(app, B):
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _handle(u, c, B)),
        group=-200,
    )
