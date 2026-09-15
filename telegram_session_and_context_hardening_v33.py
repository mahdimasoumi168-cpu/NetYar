"""Session/context hardening for the real Telegram runtime.

Goals:
- Partner logout is final: clear authentication/session keys immediately.
- Re-entering the partner panel always asks for fresh credentials.
- Cancel from any partner flow returns to the partner panel, not the public menu.
- Legacy text-router paths follow the same rules as ui2 callbacks.
"""
import logging

log = logging.getLogger("netyar.telegram.session_v33")


def _partner_active(st):
    return bool(st.get("partner_id") and st.get("partner_active") is True and not st.get("partner_logged_out"))


def install(app, B):
    if getattr(B, "_session_context_hardening_v33", False):
        return True

    old_cancel = getattr(B, "cancel", None)

    async def cancel(update, context):
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        msg = getattr(update, "effective_message", None)
        if uid is None or msg is None:
            return None
        st = B.S.setdefault(uid, {})
        lang = st.get("lang", "fa")
        if _partner_active(st):
            st["mode"] = None
            st["step"] = None
            for k in (
                "gov_files", "gov_answers", "gov_doc_type", "print_files",
                "irancell", "irancell_phone", "final_chat_admin", "final_chat_partner_id",
            ):
                st.pop(k, None)
            try:
                import telegram_management_only_v32 as M32
                markup = M32.partner_menu(B, uid)
            except Exception:
                markup = B.partner_kb(lang)
            await msg.reply_text("❌ عملیات لغو شد.", reply_markup=markup)
            return True
        if callable(old_cancel):
            return await old_cancel(update, context)
        return None

    B.cancel = cancel

    async def partner_exit(update, context):
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        msg = getattr(update, "effective_message", None)
        if uid is None or msg is None:
            return None
        st = B.S.setdefault(uid, {})
        lang = st.get("lang", "fa")
        for k in (
            "partner", "partner_id", "partner_active", "partner_phone", "phone",
            "partner_logged_out", "night_phone", "night_partner_id", "mode", "step",
            "final_chat_admin", "final_chat_partner_id", "irancell", "irancell_phone",
        ):
            st.pop(k, None)
        st.clear()
        st["lang"] = lang
        st["partner_logged_out"] = True
        await msg.reply_text(
            "✅ از پنل همکاران به‌طور کامل خارج شدید.\n\n"
            "🔐 برای ورود مجدد باید دوباره شماره موبایل و رمز عبور همکار را وارد کنید.",
            reply_markup=B.main(uid),
        )
        return True

    B.partner_exit = partner_exit

    try:
        import telegram_absolute_callback_hardening_v30 as V30
        old_dispatch = V30._dispatch
        if not getattr(V30, "_session_dispatch_v33", False):
            async def dispatch(update, context, BB, label):
                label = str(label or "").strip()
                if label == "❌ انصراف":
                    uid = update.callback_query.from_user.id
                    st = BB.S.setdefault(uid, {})
                    lang = st.get("lang", "fa")
                    if _partner_active(st):
                        st["mode"] = None
                        st["step"] = None
                        for k in (
                            "gov_files", "gov_answers", "gov_doc_type", "print_files",
                            "irancell", "irancell_phone", "final_chat_admin", "final_chat_partner_id",
                        ):
                            st.pop(k, None)
                        try:
                            import telegram_management_only_v32 as M32
                            markup = M32.partner_menu(BB, uid)
                        except Exception:
                            markup = BB.partner_kb(lang)
                        try:
                            await update.callback_query.answer()
                        except Exception:
                            pass
                        await update.callback_query.message.reply_text("❌ عملیات لغو شد.", reply_markup=markup)
                        return
                    return await old_dispatch(update, context, BB, label)
                if label == "🚪 خروج از پنل":
                    return await partner_exit(update, context)
                return await old_dispatch(update, context, BB, label)
            V30._dispatch = dispatch
            V30._session_dispatch_v33 = True
    except Exception:
        log.exception("v30 session dispatch patch unavailable")

    B._session_context_hardening_v33 = True
    log.info("REAL runtime: session/context hardening v33 installed")
    return True
