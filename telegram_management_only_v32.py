"""Final management-only partner UI and reliable two-way chat overlay."""
import inspect
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.management_only_v32")
MANAGEMENT = "💬 ارتباط با مدیریت"
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
CANCEL = "❌ انصراف"
TICKET_LABELS = {
    "🎫 تیکت به مدیریت",
    "✉️ ارسال تیکت به مدیریت",
    "✉️ تیکت به مدیریت",
    "🎫 ارسال تیکت",
    "🎫 Ticket to admin",
    "✉️ Ticket to admin",
}


def partner_menu(B, uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([
            ["➕ شارژ حساب", IRANCELL],
            ["🏛 حل مشکل سامانه دولت من", "🎫 درخواست‌های من"],
            ["📱 خدمات سیم کارت", "🪪 فیدای غیر حضوری"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی"],
            [MANAGEMENT],
            ["🚪 خروج از پنل"],
            [CANCEL],
        ], B, uid)
    except Exception:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(IRANCELL, callback_data="__never__")],
            [InlineKeyboardButton(MANAGEMENT, callback_data="__never__")],
            [InlineKeyboardButton(CANCEL, callback_data="__never__")],
        ])


def install(app, B):
    if getattr(B, "_management_only_v32", False):
        return True

    # Make every live partner keyboard resolve to the single management chat.
    def _partner_kb(lang="fa"):
        uid = 0
        try:
            import telegram_ui_policy_v2 as UI
            uid = int(UI._uid() or 0)
        except Exception:
            pass
        return partner_menu(B, uid)
    B.partner_kb = _partner_kb

    # The closed-hours gate owns its own menu function; replace it too.
    try:
        import telegram_offhours_partner_gate_v2 as G
        G._night_partner_markup = partner_menu
    except Exception:
        log.exception("night partner menu patch failed")

    # v31 has a private night-menu helper; patch it so the service list cannot
    # reintroduce the removed ticket button.
    try:
        import telegram_partner_runtime_fix_v31 as V31
        V31._night_menu = partner_menu
    except Exception:
        log.exception("v31 night menu patch failed")

    # Any legacy dispatcher route for ticket is disabled. The only supported
    # partner communication path is MANAGEMENT.
    try:
        import telegram_ui_policy_v2 as UI
        old_dispatch = UI._dispatch
        if not getattr(UI, "_management_only_dispatch_v32", False):
            async def dispatch(update, context, BB, label):
                label = str(label or "").strip()
                if label in TICKET_LABELS:
                    uid = getattr(getattr(update, "effective_user", None), "id", None)
                    msg = getattr(update, "effective_message", None)
                    if msg:
                        await msg.reply_text(
                            "ℹ️ برای ارتباط با مدیریت فقط از گزینه «💬 ارتباط با مدیریت» استفاده کنید.",
                            reply_markup=partner_menu(BB, int(uid or 0)),
                        )
                    raise ApplicationHandlerStop
                result = old_dispatch(update, context, BB, label)
                if inspect.isawaitable(result):
                    return await result
                return result
            UI._dispatch = dispatch
            UI._management_only_dispatch_v32 = True
    except Exception:
        log.exception("management-only dispatch patch failed")

    # Repair the v31-created off:partner callback after module load.
    try:
        async def off_partner_clean(update, context):
            q = getattr(update, "callback_query", None)
            if not q or str(q.data or "") != "off:partner":
                return
            try:
                from telegram_offhours_partner_gate_v2 import _is_open, _active_partner_session, is_night_worker
                if _is_open(B):
                    return
                uid = q.from_user.id
                if not (_active_partner_session(B, uid) and is_night_worker(B, uid)):
                    return
            except Exception:
                return
            try:
                await q.answer()
            except Exception:
                pass
            await q.message.reply_text("🌙 پنل همکاران شیفت شب فعال است.", reply_markup=partner_menu(B, q.from_user.id))
            raise ApplicationHandlerStop
        app.add_handler(CallbackQueryHandler(off_partner_clean, pattern=r"^off:partner$"), group=-31002)
    except Exception:
        log.exception("off-hours management-only callback patch failed")

    B._management_only_v32 = True
    log.info("Management-only partner UI v32 installed")
    return True
