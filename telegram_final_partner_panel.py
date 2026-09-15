"""Final canonical partner panel.

Rules:
- Every explicit entry into the partner panel starts a fresh authentication.
- Logout clears all partner credentials/session state and returns to the public UI.
- The partner panel keeps the complete legacy option set plus the Irancell SIM problem service.
- ui2 callback routing is wrapped once, without registering duplicate callback handlers.
"""
import logging

log = logging.getLogger("netyar.telegram.final_partner_panel")

PARTNER_LABELS = {
    "👥 پنل همکاران", "👥 Partner panel", "👥 لوحة الشركاء"
}
LOGOUT_LABELS = {
    "🚪 خروج از پنل", "🚪 Exit panel", "🔒 خروج دائمی",
    "🔒 Permanent logout", "🔒 تسجيل الخروج الدائم"
}
IRANCELL_LABEL = "📱 حل مشکل سیم کارت ایرانسل"


def _clear_partner_session(B, uid):
    old = dict(B.S.get(uid, {}) or {})
    keep = {}
    for key in ("lang", "status", "citizenship"):
        if old.get(key) is not None:
            keep[key] = old[key]
    keep["partner_logged_out"] = True
    keep["mode"] = None
    B.S[uid] = keep
    return keep


def _partner_keyboard(UI, B, uid):
    return UI.inline([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        [IRANCELL_LABEL, "🪪 فیدای غیر حضوری"],
        ["🔎 پیگیری کد", "📋 سوابق"],
        ["💰 موجودی", "🎫 تیکت به مدیریت"],
        ["🚪 خروج از پنل"],
        ["❌ انصراف"],
    ], B, uid)


def install(app, B):
    if getattr(B, "_final_partner_panel_v1", False):
        return
    import telegram_ui_policy_v2 as UI

    # Always render the complete partner menu. Do not allow later legacy
    # wrappers to collapse it to only two or three options.
    B.partner_kb = lambda lang="fa": _partner_keyboard(UI, B, UI._uid() or 0)

    original_dispatch = UI._dispatch

    async def dispatch(update, context, bot, label):
        q = getattr(update, "callback_query", None)
        uid = q.from_user.id if q else update.effective_user.id
        label = str(label or "").strip()

        if label in LOGOUT_LABELS:
            st = _clear_partner_session(bot, uid)
            try:
                if q:
                    await q.answer("🔒 از پنل همکاران خارج شدید.")
                    return await q.message.reply_text(
                        "🔒 خروج از پنل با موفقیت انجام شد.\n\n"
                        "برای ورود دوباره باید شماره موبایل و اطلاعات ورود همکار را مجدداً وارد کنید.",
                        reply_markup=bot.main(uid),
                    )
                return await update.effective_message.reply_text(
                    "🔒 خروج از پنل با موفقیت انجام شد.",
                    reply_markup=bot.main(uid),
                )
            except Exception:
                log.exception("partner logout failed")
                try:
                    return await update.effective_message.reply_text("🔒 خروج انجام شد. لطفاً از منوی اصلی وارد پنل همکاران شوید.")
                except Exception:
                    return None

        if label in PARTNER_LABELS:
            # Explicit panel entry is always a fresh login. This prevents a
            # previous authenticated session/link from silently reopening the
            # panel without asking for phone and password again.
            st = _clear_partner_session(bot, uid)
            st["mode"] = "p_phone"
            st["step"] = "partner_phone"
            if q:
                await q.answer()
                return await q.message.reply_text(
                    "👥 ورود به پنل همکاران\n\n"
                    "📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
                    reply_markup=bot.cancel_kb(st.get("lang", "fa")),
                )

        # The dedicated Irancell module owns the service flow (phone -> ID
        # document -> balance debit -> admin notification). Delegating here
        # preserves that implementation while keeping the button visible in
        # the final canonical partner keyboard.
        return await original_dispatch(update, context, bot, label)

    UI._dispatch = dispatch
    B._final_partner_panel_v1 = True
