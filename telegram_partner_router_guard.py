"""Guard the Telegram partner panel against legacy keyboard wrappers."""
import logging
log = logging.getLogger("netyar.telegram.partner_router_guard")


def _apply(B, UI):
    def partner_kb(lang="fa"):
        uid = getattr(UI, "_uid", lambda: None)()
        if uid is None:
            uid = getattr(B, "_ui_current_uid", None) or 0
        return UI.inline([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)
    B.partner_kb = partner_kb
    try:
        import telegram_business_features as F
        F._partner_kb = lambda: partner_kb()
    except Exception:
        log.exception("partner keyboard guard could not update business layer")


def install():
    import bot as B
    import telegram_ui_policy_v2 as UI
    if getattr(UI, "_partner_router_guard", False):
        _apply(B, UI)
        return
    original = UI.install
    def guarded_install(app, bot):
        result = original(app, bot)
        _apply(bot, UI)
        return result
    UI.install = guarded_install
    UI._partner_router_guard = True
    if getattr(B, "_inline_ui_v2", False):
        _apply(B, UI)
    log.info("Telegram partner router guard installed")
