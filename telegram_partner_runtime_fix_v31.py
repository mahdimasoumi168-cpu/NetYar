"""Runtime v31 partner fixes.

Installs the partner chat relay in the real Telegram runtime and provides an
explicit night-shift partner menu that includes the Irancell issue service.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_runtime_v31")
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
MANAGEMENT = "💬 ارتباط با مدیریت"


def _night_menu(B, uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([
            ["➕ شارژ حساب", IRANCELL],
            ["🏛 حل مشکل سامانه دولت من", "🔎 پیگیری کد"],
            ["📋 سوابق", "💰 موجودی"],
            ["📱 خدمات سیم کارت", "🪪 فیدای غیر حضوری"],
            ["🎫 تیکت به مدیریت", MANAGEMENT],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)
    except Exception:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(IRANCELL, callback_data="__never__")],
            [InlineKeyboardButton(MANAGEMENT, callback_data="__never__")],
        ])


def install(app, B):
    if getattr(B, "_partner_runtime_v31", False):
        return True

    # This relay must be installed in the actual runtime; its own handlers
    # live at priorities earlier than the generic off-hours message gate.
    try:
        import telegram_partner_chat_reliability as CR
        CR.install(app, B)
        log.info("REAL runtime: partner chat reliability installed")
    except Exception:
        log.exception("partner chat reliability unavailable")

    # Explicitly repair the closed-hours partner-panel menu. The previous
    # night-shift gate used a hand-written keyboard that omitted Irancell.
    try:
        import telegram_offhours_partner_gate_v2 as G
        async def cb(update, context):
            q = getattr(update, "callback_query", None)
            if not q or str(q.data or "") != "off:partner":
                return
            try:
                if G._is_open(B):
                    return
            except Exception:
                return
            uid = q.from_user.id
            active = G._active_partner_session(B, uid)
            if not active or not G.is_night_worker(B, uid):
                return
            try:
                await q.answer()
            except Exception:
                pass
            await q.message.reply_text("🌙 پنل همکاران شیفت شب فعال است.", reply_markup=_night_menu(B, uid))
            raise ApplicationHandlerStop
        app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:partner$"), group=-31001)
    except Exception:
        log.exception("night partner menu hotfix unavailable")

    B._partner_runtime_v31 = True
    return True
