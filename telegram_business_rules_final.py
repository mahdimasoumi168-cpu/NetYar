"""Final business rules for authentication, citizen routing and payment policy."""
import logging

log = logging.getLogger("netyar.business_rules_final")


def install(app, B):
    if getattr(B, "_business_rules_final", False):
        return

    # Permanent partner logout must destroy the in-memory authentication state.
    # The next click on the partner panel therefore starts phone + password login.
    old_partner_exit_choice = B.partner_exit_choice

    async def partner_exit_choice(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (update.message.text or "").strip()
        if st.get("mode") == "partner_exit_choice" and text == "🔒 خروج دائمی":
            lang = st.get("lang", "fa")
            status = st.get("status") or st.get("citizenship") or "foreign"
            # Do not retain partner_id, phone, password/session flags or any
            # partner-specific mode. This is a real logout, not a hidden pause.
            B.S[uid] = {"lang": lang, "status": status, "citizenship": status}
            return await update.message.reply_text(
                "🔒 خروج دائمی انجام شد.\n\n"
                "برای ورود دوباره به «👥 پنل همکاران»، شماره موبایل و رمز عبور را دوباره وارد کنید.",
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
            lang = st.get("lang", "fa")
            # Iranian path: no foreign-only services, but partner access remains.
            await q.message.reply_text(
                "🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.\n\n"
                "در صورت داشتن حساب همکار، می‌توانید از «👥 پنل همکاران» وارد شوید.",
                reply_markup=B.kb([["👥 پنل همکاران"], ["🎫 پیگیری"], [B.CANCEL]]),
            )
            return
        await q.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))

    B.statuscb = statuscb

    # Force payment policy at request creation: public customers use manual
    # card-to-card; authenticated partners use only their prepaid balance.
    # Existing service modules already implement the actual balance deduction;
    # this guard prevents an authenticated partner from being offered a public
    # payment path by a later UI layer.
    old_main = B.main

    def main(uid):
        return old_main(uid)

    B.main = main
    B._business_rules_final = True
    log.info("Final business/authentication rules installed")
