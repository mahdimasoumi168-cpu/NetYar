"""Authoritative partner logout.

The partner-panel logout button is a real logout, not a two-step temporary
logout choice. It clears authentication/session state so the next partner
panel entry must collect phone + password again.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_logout_v31")


def install(app, B):
    if getattr(B, "_partner_logout_hardening_v31", False):
        return True

    async def hard_logout(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        lang = st.get("lang", "fa")
        status = st.get("status", "foreign")

        # Do not retain partner_id, phone, password/session tokens, modes,
        # service continuation state, or night-shift authentication.
        B.S[uid] = {
            "lang": lang,
            "status": status,
            "citizenship": status,
            "partner_logged_out": True,
            "mode": None,
        }
        try:
            await update.effective_message.reply_text(
                "🔒 خروج کامل از پنل همکاران انجام شد.\n\n"
                "برای ورود دوباره، «👥 پنل همکاران» را انتخاب کنید و شماره موبایل و رمز عبور را دوباره وارد کنید.",
                reply_markup=B.main(uid),
            )
        except Exception:
            log.exception("hard partner logout reply failed")

    # The canonical UI dispatcher and v30 both call B.partner_exit. Rebind it
    # after all legacy logout wrappers have been installed.
    B.partner_exit = hard_logout
    B._partner_logout_hardening_v31 = True
    log.info("Authoritative full partner logout v31 installed")
    return True
