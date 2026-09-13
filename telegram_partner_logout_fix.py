"""Keep partner logout from immediately re-entering the login/profile flow."""


def install(B):
    if getattr(B, "_partner_logout_fix_installed", False):
        return

    original = B.partner_exit_choice

    async def partner_exit_choice(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (getattr(update.message, "text", "") or "").strip()

        if st.get("mode") == "partner_exit_choice" and text == "🔒 خروج دائمی":
            # Clear authentication and every pending login/profile state.
            # IMPORTANT: do not set p_phone here. The user must explicitly
            # press «👥 پنل همکاران» to start a new login.
            lang = st.get("lang", "fa")
            status = st.get("status", "foreign")
            B.S[uid] = {"lang": lang, "status": status, "citizenship": status}
            return await update.message.reply_text(
                "🔒 خروج از پنل با موفقیت انجام شد.\n\n"
                "برای ورود دوباره، خودتان دکمه «👥 پنل همکاران» را انتخاب کنید.",
                reply_markup=B.main(uid),
            )

        return await original(update, context)

    B.partner_exit_choice = partner_exit_choice
    B._partner_logout_fix_installed = True
