"""Absolute Telegram off-hours start/restart guard.

This is an additive safety layer. It does not change the existing menus during
working hours and does not replace the partner-panel flow. Outside working
hours, /start and restart are always blocked; entering the night partner panel
is possible only through the dedicated "👥 پنل همکاران" button and its fresh
credential flow.
"""
import logging
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.offhours.absolute_start_guard")


def install(app, B):
    if getattr(B, "_absolute_offhours_start_guard", False):
        return True

    try:
        from telegram_offhours_partner_gate_v2 import _is_open, _closed_text, _closed_markup
    except Exception:
        log.exception("canonical off-hours gate unavailable")
        return False

    def closed():
        try:
            return not bool(_is_open(B))
        except Exception:
            return True

    async def start(update, context):
        user = getattr(update, "effective_user", None)
        msg = getattr(update, "effective_message", None)
        if not user or not msg or not closed():
            return
        await msg.reply_text(_closed_text(B), reply_markup=_closed_markup())
        raise ApplicationHandlerStop

    async def start_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        data = str(q.data or "").strip().lower()
        if data not in {"start", "restart", "start:restart", "main:restart", "home:restart"}:
            return
        if not closed():
            return
        try:
            await q.answer("❌ خارج از ساعت کاری است.", show_alert=True)
        except Exception:
            pass
        if q.message:
            await q.message.reply_text(_closed_text(B), reply_markup=_closed_markup())
        raise ApplicationHandlerStop

    # Highest-priority handlers: /start and recognized restart callbacks can
    # never fall through to the public main-menu handler while closed.
    app.add_handler(CommandHandler("start", start), group=-50000)
    app.add_handler(CallbackQueryHandler(start_callback), group=-49999)
    B._absolute_offhours_start_guard = True
    return True
