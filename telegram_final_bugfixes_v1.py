"""Final compatibility fixes applied after legacy Telegram overlays."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

def _menu_without_manual_payment(rid, paid=False):
    rows=[
        [InlineKeyboardButton("🔎 جزئیات کامل",callback_data=f"rq:detail:{rid}")],
        [InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")],
    ]
    if paid:
        rows.append([InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"rq:approve:{rid}")])
    else:
        rows.append([InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}")])
    rows.append([InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")])
    return InlineKeyboardMarkup(rows)

def install(app,B):
    if getattr(B,'_final_bugfixes_v1',False): return
    try:
        import telegram_request_control_v2 as R
        R.menu=_menu_without_manual_payment
    except Exception:
        pass
    async def obsolete_payment(update,context):
        q=update.callback_query
        if not q:return
        d=str(q.data or '')
        if not d.startswith('rq:payconfirm:'):return
        await q.answer('این گزینه حذف شده است؛ پرداخت این خدمت از اعتبار همکار انجام می‌شود.',show_alert=True)
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(obsolete_payment,pattern=r'^rq:payconfirm:\d+$'),group=-2500000)
    B._final_bugfixes_v1=True
