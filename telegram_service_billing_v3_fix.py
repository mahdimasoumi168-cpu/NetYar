"""Final activation layer for the remaining FIDA billing flow.
Print and SIM services are intentionally removed from the live partner menu.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

FIDA_PRICE=400000

def install(app,B):
    if getattr(B,"_svc3_fix_installed",False): return
    import telegram_service_billing_v3 as V
    # Do not allow old DB/admin price values to silently replace the requested prices.
    def exact_price(_B,key,default):
        if key=="price_fida": return FIDA_PRICE
        return default
    V._price=exact_price
    # Live partner menu: only services that are still active.
    def partner_kb(lang="fa"):
        return B.kb([
            ["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],
            ["🪪 فیدای غیر حضوری","🔎 پیگیری کد"],
            ["📋 سوابق","💰 موجودی"],
            ["🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
        ])
    B.partner_kb=partner_kb
    V.install(app,B)
    # V.install replaces B.fida/B.sim_start; restore the partner keyboard after that.
    B.partner_kb=partner_kb
    B._svc3_fix_installed=True
