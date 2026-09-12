"""Telegram UI policy: no ReplyKeyboard is used in production.

All menu choices are attached to the message as inline buttons. The labels are
kept in code, so deploys/restarts do not erase the menu definition.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def _inline(rows):
    out=[]
    for row in rows or []:
        buttons=[]
        for item in row or []:
            label=str(item[0] if isinstance(item,(tuple,list)) else item)
            buttons.append(InlineKeyboardButton(label, callback_data="ui:"+label[:55]))
        if buttons: out.append(buttons)
    return InlineKeyboardMarkup(out)


def install(B):
    if getattr(B,"_inline_ui_policy",False): return
    B.kb=_inline
    B._inline_ui_policy=True

    # The partner ticket module uses its own keyboard constructor; make it obey
    # the same inline-only policy without changing its routing logic.
    try:
        import telegram_business_features as F
        F._partner_kb=lambda: _inline([
            ["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد","📋 سوابق"],
            ["💰 موجودی","🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],["❌ انصراف"],
        ])
    except Exception:
        pass
