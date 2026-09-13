"""Final Telegram partner-panel lock.

Installed last in the canonical runtime so legacy feature layers cannot
replace the partner keyboard with an incompatible wrapper.
"""
import logging
log = logging.getLogger("netyar.telegram.partner_final_lock")


def install(app, B):
    if getattr(B, "_partner_final_lock", False):
        return
    import telegram_ui_policy_v2 as UI

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
        log.exception("partner business keyboard lock failed")

    B._partner_final_lock = True
    log.info("Final Telegram partner keyboard lock active")
