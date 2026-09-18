"""Keep partner logout from immediately re-entering the login/profile flow."""


def install(B):
    if getattr(B, "_partner_logout_fix_installed", False):
        return

    original = B.partner_exit_choice

    async def partner_exit_choice(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = (getattr(update.message, "text", "") or "").strip()

        if st.get("mode") == "partner_exit_choice" and text in {
            "🔒 خروج دائمی",
            "🔒 Permanent logout",
            "🔒 تسجيل الخروج الدائم",
        }:
            # Clear authentication and every pending login/profile state.
            # Keep only the user's selected language/citizenship context.
            # The partner UI layer uses partner_logged_out to prevent automatic
            # relinking through partner_telegram_links.
            lang = st.get("lang", "fa")
            status = st.get("status", "foreign")
            B.S[uid] = {
                "lang": lang,
                "status": status,
                "citizenship": status,
                "partner_logged_out": True,
            }
            # Persist the explicit permanent logout so a bot restart cannot
            # silently relink this Telegram account to its remembered partner.
            try:
                B.db.set_setting("partner_logout:" + str(uid), "1")
            except Exception:
                pass
            return await update.message.reply_text(
                "🔒 خروج از پنل با موفقیت انجام شد.\n\n"
                "برای ورود دوباره، خودتان دکمه «👥 پنل همکاران» را انتخاب کنید.",
                reply_markup=B.main(uid),
            )

        return await original(update, context)

    B.partner_exit_choice = partner_exit_choice
    B._partner_logout_fix_installed = True
