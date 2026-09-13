"""Final activation layer for FIDA/SIM billing v3.
Keeps exact requested prices and exposes SIM inside the partner panel.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

SIM_PRICES={"سامانتل":560000,"ایرانسل":860000,"رایتل":860000}
FIDA_PRICE=400000

def install(app,B):
    if getattr(B,"_svc3_fix_installed",False): return
    import telegram_service_billing_v3 as V
    # Do not allow old DB/admin price values to silently replace the requested prices.
    def exact_price(_B,key,default):
        if key=="price_fida": return FIDA_PRICE
        return {"sim_price_samantel":560000,"sim_price_irancell":860000,"sim_price_rightel":860000}.get(key,default)
    V._price=exact_price
    # The partner panel must expose every operational service, including SIM.
    def partner_kb(lang="fa"):
        return B.kb([
            ["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],
            ["📱 خدمات سیم کارت","🪪 فیدای غیر حضوری"],
            ["🔎 پیگیری کد","📋 سوابق"],
            ["💰 موجودی","🎫 تیکت به مدیریت"],
            ["🚪 خروج از پنل"],
        ])
    B.partner_kb=partner_kb
    # Make the existing v3 partner-pay action reachable before its generic callback.
    async def partner_pay(update,context):
        if str(getattr(update.callback_query,"data", ""))!="svc3:sim_partner_pay": return
        await V.pay_cb(update,context,B)
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(partner_pay,pattern=r"^svc3:sim_partner_pay$"),group=-6000)
    V.install(app,B)
    # V.install replaces B.fida/B.sim_start; restore the partner keyboard after that.
    B.partner_kb=partner_kb
    B._svc3_fix_installed=True
