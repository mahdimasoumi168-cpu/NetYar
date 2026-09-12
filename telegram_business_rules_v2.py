"""Final authentication/citizenship rules for Telegram."""
import logging
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop
log = logging.getLogger("netyar.business_rules_v2")

def install(app, B):
    if getattr(B, "_business_rules_v2", False): return

    async def exit_handler(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "partner_exit_choice": return
        text = (update.message.text or "").strip()
        if text == "🔒 خروج دائمی":
            lang = st.get("lang", "fa")
            status = st.get("status") or st.get("citizenship") or "foreign"
            # Hard reset: no partner_id, phone, active flag, password/session state.
            B.S[uid] = {"lang": lang, "status": status, "citizenship": status}
            await update.message.reply_text(
                "🔒 خروج دائمی انجام شد.\n\nبرای ورود دوباره به «👥 پنل همکاران»، شماره موبایل و رمز عبور را دوباره وارد کنید.",
                reply_markup=B.main(uid),
            )
            raise ApplicationHandlerStop

    async def status_handler(update, context):
        q = update.callback_query
        if not q or not str(q.data).startswith("st:"): return
        await q.answer()
        uid = q.from_user.id
        status = str(q.data).split(":",1)[1]
        st = B.S.setdefault(uid,{})
        st.update(status=status, citizenship=status)
        if status == "iranian":
            await q.message.reply_text(
                "🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.\n\nدر صورت داشتن حساب همکار، می‌توانید از «👥 پنل همکاران» وارد شوید.",
                reply_markup=B.kb([["👥 پنل همکاران"],["🎫 پیگیری"],[B.CANCEL]]),
            )
        else:
            await q.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, exit_handler), group=-5000)
    app.add_handler(CallbackQueryHandler(status_handler, pattern=r"^st:"), group=-5000)
    B._business_rules_v2 = True
    log.info("Business rules v2 installed")
