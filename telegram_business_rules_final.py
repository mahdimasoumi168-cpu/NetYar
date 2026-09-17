"""Final business rules for authentication, citizen routing and payment policy."""
import logging

log = logging.getLogger("netyar.business_rules_final")


def install(app, B):
    if getattr(B, "_business_rules_final", False):
        return

    # Any explicit exit from the partner panel is a real logout.
    # The next click on the partner panel must require phone + password again.
    old_partner_exit_choice = B.partner_exit_choice

    async def partner_exit_choice(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (update.message.text or "").strip()
        exit_labels = {
            "⏸ خروج موقت",
            "🔒 خروج دائمی",
            "🚪 خروج از پنل",
            "🚪 خروج",
            "Exit panel",
            "🚪 Exit partner panel",
        }
        if st.get("mode") == "partner_exit_choice" and text in exit_labels:
            lang = st.get("lang", "fa")
            status = st.get("status") or st.get("citizenship") or "foreign"
            # Remove every partner authentication/session field. Keep only the
            # public identity/language state needed to render the main menu.
            B.S[uid] = {
                "lang": lang,
                "status": status,
                "citizenship": status,
                "partner_logged_out": True,
                "partner_active": False,
                "mode": None,
                "step": None,
            }
            return await update.message.reply_text(
                "🚪 خروج از پنل با موفقیت انجام شد.\n\n"
                "برای ورود دوباره به «👥 پنل همکاران»، شماره موبایل اختصاصی و رمز عبور را دوباره وارد کنید.",
                reply_markup=B.main(uid),
            )
        return await old_partner_exit_choice(update, context)

    B.partner_exit_choice = partner_exit_choice

    # Iranian users must not accidentally receive the foreign-citizen service menu.
    # Keep the partner panel available, as requested, and make the wording clear.
    old_statuscb = B.statuscb

    async def statuscb(update, context):
        q = update.callback_query
        if not q:
            return await old_statuscb(update, context)
        await q.answer()
        uid = q.from_user.id
        status = q.data.split(":", 1)[1]
        st = B.S.setdefault(uid, {})
        st["status"] = status
        st["citizenship"] = status
        if status == "iranian":
            await q.message.reply_text(
                "🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.\n\n"
                "در صورت داشتن حساب همکار، می‌توانید از «👥 پنل همکاران» وارد شوید.",
                reply_markup=B.kb([["👥 پنل همکاران"], ["🎫 پیگیری"], [B.CANCEL]]),
            )
            return
        await q.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))

    B.statuscb = statuscb

    old_main = B.main

    def main(uid):
        return old_main(uid)

    B.main = main
    B._business_rules_final = True
    log.info("Final business/authentication rules installed")
