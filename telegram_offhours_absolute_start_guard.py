"""Absolute Telegram off-hours start/restart guard.

This is an additive safety layer. It does not change the existing menus during
working hours and does not replace the partner-panel flow. Outside working
hours, /start, start/restart callbacks and ordinary service entry points are
blocked before they can open the public main menu. The only exception is an
explicitly authenticated night-shift partner/admin context.
"""
import logging
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.offhours.absolute_start_guard")


def install(app, B):
    if getattr(B, "_absolute_offhours_start_guard", False):
        return True

    try:
        from telegram_offhours_partner_gate_v2 import _is_open, _allowed_during_closed, _closed_text, _markup
    except Exception:
        log.exception("canonical off-hours gate unavailable")
        return False

    def blocked(uid):
        try:
            return (not _is_open(B)) and (not _allowed_during_closed(B, uid))
        except Exception:
            # Fail closed. A malformed clock/config must never expose services.
            return True

    async def start(update, context):
        user = getattr(update, "effective_user", None)
        msg = getattr(update, "effective_message", None)
        if not user or not msg or not blocked(user.id):
            return
        await msg.reply_text(_closed_text(B), reply_markup=_markup())
        raise ApplicationHandlerStop

    async def start_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        data = str(q.data or "").strip().lower()
        if data not in {"start", "restart", "start:restart", "main:restart", "home:restart"}:
            return
        if not blocked(q.from_user.id):
            return
        try:
            await q.answer("⏰ خارج از ساعت کاری است.", show_alert=True)
        except Exception:
            pass
        if q.message:
            await q.message.reply_text(_closed_text(B), reply_markup=_markup())
        raise ApplicationHandlerStop

    # Highest-priority handlers: they must run before normal /start/menu logic.
    app.add_handler(CommandHandler("start", start), group=-50000)
    app.add_handler(CallbackQueryHandler(start_callback), group=-49999)
    B._absolute_offhours_start_guard = True
    return True
