"""Night-shift stability overlay.

The old closed-hours gate only allowed callbacks/messages while mode ==
'partner'. Service data-entry modes (phone, document, management chat, etc.)
were therefore rejected after a valid night login. This overlay changes the
gate to the real authorization rule: an active partner explicitly enabled for
night shift may continue any partner service until logout. Public users remain
fully blocked.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.night_shift_stability_v26")
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"


def _active_night(B, uid):
    try:
        import telegram_offhours_partner_gate_v2 as G
        return bool(G.is_night_worker(B, uid) and G._active_partner_session(B, uid))
    except Exception:
        return False


def _night_markup(B, uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            [IRANCELL, "🪪 فیدای غیر حضوری"],
            ["📱 خدمات سیم کارت", "🔎 پیگیری کد"],
            ["📋 سوابق", "💰 موجودی"],
            ["🎫 تیکت به مدیریت", "💬 ارتباط با مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)
    except Exception:
        return None


def install(app, B):
    if getattr(B, "_night_shift_stability_v26", False):
        return
    try:
        import telegram_offhours_partner_gate_v2 as G
        original_gate = G.message_gate

        async def stable_message_gate(update, context, BB):
            if G._is_open(BB):
                return
            user = getattr(update, "effective_user", None)
            msg = getattr(update, "effective_message", None)
            if not user or not msg:
                return
            if _active_night(BB, user.id):
                return
            await msg.reply_text(G._closed_text(BB), reply_markup=G._closed_markup())
            raise ApplicationHandlerStop

        G.message_gate = stable_message_gate

        async def stable_callback_gate(update, context):
            if G._is_open(B):
                return
            q = getattr(update, "callback_query", None)
            if not q:
                return
            uid = q.from_user.id
            data = str(q.data or "")
            if data in {"off:restart", "off:partner"}:
                return
            if _active_night(B, uid):
                return
            try:
                await q.answer("❌ خارج از ساعت کاری است و این عملیات مجاز نیست.", show_alert=True)
            except Exception:
                pass
            await q.message.reply_text(G._closed_text(B), reply_markup=G._closed_markup())
            raise ApplicationHandlerStop

        # Replace the already-registered gate callbacks rather than stacking
        # another gate, so every later service handler keeps its normal order.
        for group, callback in ((-29998, stable_message_gate), (-29997, stable_callback_gate)):
            for handler in app.handlers.get(group, []):
                handler.callback = callback

        # Replace only the closed-hours partner-entry callback. This guarantees
        # the complete current partner keyboard, including Irancell, is shown
        # when an authenticated night worker opens the panel again.
        handlers = app.handlers.get(-30000, [])
        for handler in handlers:
            old = handler.callback
            async def stable_off_callback(update, context, _old=old):
                q = getattr(update, "callback_query", None)
                if q and str(q.data or "") == "off:partner" and not G._is_open(B) and _active_night(B, q.from_user.id):
                    await q.answer()
                    await q.message.reply_text("🌙 پنل همکاران شیفت شب فعال است.", reply_markup=_night_markup(B, q.from_user.id))
                    raise ApplicationHandlerStop
                return await _old(update, context)
            handler.callback = stable_off_callback

    except Exception:
        log.exception("night shift stability overlay installation failed")
    B._night_shift_stability_v26 = True
    log.info("Night shift stability v26 installed")
