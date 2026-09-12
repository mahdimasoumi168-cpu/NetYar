"""Final Telegram partner UI adapter.

All partner controls are rendered as inline buttons. The only persistent
ReplyKeyboard control remains the global restart button owned by
telegram_ui_policy_v2.
"""

def install(app, B):
    if getattr(B, "_partner_ui_fix", False):
        return
    import telegram_business_features as F
    import telegram_ui_policy_v2 as UI

    def partner_inline(uid=None):
        return UI.inline([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی", "🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)

    # business_features._send_ticket_prompt calls its private keyboard directly,
    # so patch that constructor too, not only B.partner_kb.
    F._partner_kb = lambda: partner_inline()
    B.partner_kb = lambda lang="fa": partner_inline()
    B._partner_ui_fix = True
