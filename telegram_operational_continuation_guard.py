"""High-priority continuation bridge for partner services and management chat.

The partner management chat has one canonical entry point only:
"💬 ارتباط با مدیریت".  Legacy ticket labels are still accepted internally,
but they are never exposed as a second button.  The partner stays in the same
panel/state instead of being bounced to another menu after an error.
"""
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

SERVICE_MODES = {
    "svc3_name", "svc3_fida", "svc3_fida_code", "svc3_fida_photo", "svc3_fida_receipt",
    "svc3_sim_carrier", "svc3_sim_photo", "svc3_sim_pay", "svc3_sim_receipt",
    "svc3_home", "svc3_home_post", "svc3_home_plate", "svc3_ship", "svc3_ship_post",
    "svc3_ship_plate", "svc3_phone",
}

COMMUNICATION_LABELS = {
    "💬 ارتباط با مدیریت",
    "✉️ تیکت به مدیریت",
    "📨 ارسال پیام به مدیریت",
    "✉️ ارسال تیکت به مدیریت",
    "📝 تیکت به مدیریت",
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
            # Keep the user in the current service instead of returning to the
            # main menu.  The existing mode is deliberately preserved.
            await msg.reply_text("❌ ادامه خدمت با خطا مواجه شد. لطفاً همان مورد را دوباره ارسال کنید.")
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
            await msg.reply_text("❌ دریافت فایل انجام نشد. لطفاً همان فایل را دوباره ارسال کنید.")
        raise ApplicationHandlerStop

    async def admin_chat_button(update, context):
        msg = update.effective_message
        if not msg or msg.text not in COMMUNICATION_LABELS:
            return
        st = B.S.setdefault(update.effective_user.id, {})
        pid = st.get("partner_id")
        if not pid:
            await msg.reply_text("⛔ ابتدا وارد پنل همکاران شوید.")
            raise ApplicationHandlerStop

        # Save the authoritative partner chat immediately. This is what the
        # admin-reply and media layers use to route every later message back to
        # this exact partner.
        try:
            B.db.set_setting(f"partner_chat_{int(pid)}", str(update.effective_user.id))
            row = B.db.conn.execute("SELECT phone FROM partners WHERE id=? LIMIT 1", (int(pid),)).fetchone()
            if row and row["phone"]:
                B.db.set_setting(f"partner_chat_{row['phone']}", str(update.effective_user.id))
        except Exception:
            pass

        # One persistent communication mode. Do not replace the partner panel
        # with a ticket page or a different keyboard.
        st.update(mode="final_partner_chat", final_chat_admin=None, final_chat_partner_id=int(pid))
        await msg.reply_text(
            "💬 ارتباط با مدیریت فعال شد.\n\n"
            "همین‌جا پیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\n"
            "همه پیام‌ها برای مدیریت ارسال می‌شوند.\n\n"
            "برای ادامه کار، همین پنل را نگه دارید؛ برای خروج «🚪 خروج از پنل» را بزنید.",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
        raise ApplicationHandlerStop

    def partner_kb(lang="fa"):
        # Exactly one visible management-communication button. Legacy ticket
        # aliases remain accepted by the handler above but are not rendered.
        return B.kb([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🪪 فیدای غیر حضوری", "📱 خدمات سیم کارت"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "💬 ارتباط با مدیریت"],
            ["🚪 خروج از پنل"],
        ])

    B.partner_kb = partner_kb
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.VOICE, media_continuation), group=-11000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, continuation), group=-11000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_chat_button), group=-10999)
    B._operational_continuation_guard = True
