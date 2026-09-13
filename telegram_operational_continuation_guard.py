"""High-priority continuation bridge for partner services and management chat."""
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

SERVICE_MODES = {
    "svc3_name", "svc3_fida", "svc3_fida_code", "svc3_fida_photo", "svc3_fida_receipt",
    "svc3_sim_carrier", "svc3_sim_photo", "svc3_sim_pay", "svc3_sim_receipt",
    "svc3_home", "svc3_home_post", "svc3_home_plate", "svc3_ship", "svc3_ship_post",
    "svc3_ship_plate", "svc3_phone",
}

def install(app, B):
    if getattr(B, "_operational_continuation_guard", False):
        return
    import telegram_service_billing_v3 as V

    async def continuation(update, context):
        msg = update.effective_message
        if not msg:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if mode not in SERVICE_MODES:
            return
        try:
            if msg.text:
                await V.text(update, context, B)
            elif msg.photo or msg.document or msg.video or msg.voice:
                await V.media(update, context, B)
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            await msg.reply_text("❌ ادامه خدمت با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
            raise ApplicationHandlerStop

    async def media_continuation(update, context):
        msg = update.effective_message
        if not msg:
            return
        st = B.S.setdefault(update.effective_user.id, {})
        if st.get("mode") not in SERVICE_MODES:
            return
        try:
            await V.media(update, context, B)
        except Exception:
            await msg.reply_text("❌ دریافت فایل انجام نشد. لطفاً دوباره ارسال کنید.")
        raise ApplicationHandlerStop

    async def admin_chat_button(update, context):
        msg = update.effective_message
        if not msg or msg.text != "💬 ارتباط با مدیریت":
            return
        st = B.S.setdefault(update.effective_user.id, {})
        if not st.get("partner_id"):
            await msg.reply_text("⛔ ابتدا وارد پنل همکاران شوید.")
            raise ApplicationHandlerStop
        st.update(mode="final_partner_chat", final_chat_admin=None, final_chat_partner_id=st.get("partner_id"))
        await msg.reply_text("💬 ارتباط با مدیریت فعال شد.\n\nپیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\nبرای خروج «❌ انصراف» را بزنید.")
        raise ApplicationHandlerStop

    def partner_kb(lang="fa"):
        return B.kb([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🪪 فیدای غیر حضوری", "📱 خدمات سیم کارت"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "💬 ارتباط با مدیریت"],
            ["✉️ تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
        ])

    B.partner_kb = partner_kb
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.VOICE, media_continuation), group=-11000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, continuation), group=-11000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_chat_button), group=-10999)
    B._operational_continuation_guard = True
