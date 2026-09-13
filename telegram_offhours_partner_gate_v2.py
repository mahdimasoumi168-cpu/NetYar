"""Final off-hours Telegram gate: restart + registered-partner panel entry.

During non-working hours regular customers see only Restart and Partner Panel.
The partner button never grants access by itself: the existing partner login
flow must validate the supplied phone against the active partners table.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

TZ = ZoneInfo("Asia/Tehran")
OPEN = time(7, 0)
CLOSE = time(19, 0)


def is_open():
    t = datetime.now(TZ).time()
    return OPEN <= t < CLOSE


def _markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
    ])


def _closed_text():
    return (
        "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
        "🕖 ساعت کاری: ۷ صبح تا ۷ شب به وقت تهران\n"
        "🌙 ساعت تعطیلی: ۷ شب تا ۷ صبح\n\n"
        "برای ورود به پنل همکاران، شماره موبایل اختصاصی همکار باید از قبل در سیستم ثبت شده باشد."
    )


def install(app, B):
    if getattr(B, "_offhours_partner_gate_v2", False):
        return True

    async def cb(update, context):
        q = update.callback_query
        if not q:
            return
        data = str(q.data or "")
        if data not in {"off:restart", "off:partner"}:
            return
        uid = q.from_user.id
        await q.answer()

        # Admins are never blocked by the business-hours gate.
        if B.admin(uid):
            if data == "off:partner":
                from telegram_partner_router_guard import _open_partner
                import telegram_ui_policy_v2 as UI
                return await _open_partner(update, context, B, UI)
            return await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))

        if is_open():
            if data == "off:partner":
                from telegram_partner_router_guard import _open_partner
                import telegram_ui_policy_v2 as UI
                return await _open_partner(update, context, B, UI)
            return await q.message.reply_text("🔄 شروع مجدد", reply_markup=B.main(uid))

        if data == "off:restart":
            return await q.message.reply_text(_closed_text(), reply_markup=_markup())

        # Do not mark the user as a partner here. The canonical partner login
        # flow asks for the registered phone and performs the actual database
        # validation before opening the partner menu.
        from telegram_partner_router_guard import _open_partner
        import telegram_ui_policy_v2 as UI
        return await _open_partner(update, context, B, UI)

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:(restart|partner)$"), group=-25000)
    B._offhours_partner_gate_v2 = True
    return True
