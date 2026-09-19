"""Runtime v31 partner fixes + admin off-hours bypass.

Keeps the real Telegram runtime deterministic: the partner chat relay is
installed at high priority, the night partner panel includes Irancell, and
administrators are never blocked by the public business-hours gate.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_runtime_v31")

MANAGEMENT = "💬 ارتباط با مدیریت"
RESTART = "🔄 شروع مجدد"


def _night_menu(B, uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([
    ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🏛 حل مشکل سامانه دولت من", "🔎 پیگیری کد"],
            ["📋 سوابق", "💰 موجودی"],

            ["🎫 تیکت به مدیریت", MANAGEMENT],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B, uid)
    except Exception:
        return InlineKeyboardMarkup([[InlineKeyboardButton(MANAGEMENT, callback_data="__never__")]])


def _is_admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        return False


def install(app, B):
    if getattr(B, "_partner_runtime_v31", False):
        return True

    try:
        import telegram_partner_chat_reliability as CR
        CR.install(app, B)
        log.info("REAL runtime: partner chat reliability installed")
    except Exception:
        log.exception("partner chat reliability unavailable")

    # Admins always bypass the public business-hours gate, including /start
    # and the reply-keyboard restart action.
    async def admin_start(update, context):
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        msg = getattr(update, "effective_message", None)
        if uid is None or not _is_admin(B, uid) or not msg:
            return
        await msg.reply_text("🛠 پنل مدیریت و خدمات مدیر\n\n✅ دسترسی کامل مدیر فعال است.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop

    async def admin_restart(update, context):
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        msg = getattr(update, "effective_message", None)
        if uid is None or not _is_admin(B, uid) or not msg:
            return
        await msg.reply_text("🔄 شروع مجدد مدیر\n\n✅ دسترسی کامل مدیر فعال است.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop

    app.add_handler(CommandHandler("start", admin_start), group=-10000001)
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"), admin_restart), group=-10000002)

    # Make the canonical off-hours handler neutral for admins. Other users
    # continue through the normal public/night-shift restrictions.
    try:
        import telegram_offhours_partner_gate_v2 as G
        async def admin_aware_message_gate(update, context):
            user = getattr(update, "effective_user", None)
            if user and _is_admin(B, user.id):
                return
            return
        async def admin_aware_callback_gate(update, context):
            q = getattr(update, "callback_query", None)
            if q and _is_admin(B, q.from_user.id):
                return
            return
        for handler in app.handlers.get(-29998, []):
            handler.callback = admin_aware_message_gate
        for handler in app.handlers.get(-29997, []):
            handler.callback = admin_aware_callback_gate
    except Exception:
        log.exception("admin-aware off-hours gate patch unavailable")

    # Explicitly repair the closed-hours partner-panel menu.
    try:
        import telegram_offhours_partner_gate_v2 as G
        async def cb(update, context):
            q = getattr(update, "callback_query", None)
            if not q or str(q.data or "") != "off:partner":
                return
            uid = q.from_user.id
            if _is_admin(B, uid):
                try:
                    await q.answer()
                except Exception:
                    pass
                await q.message.reply_text("🛠 پنل مدیریت فعال است.", reply_markup=B.main(uid))
                raise ApplicationHandlerStop
            try:
                if G._clock_is_open(B):
                    return
                if not G.night_shift_enabled(B):
                    await q.answer("🌙 شیفت شب بسته است.", show_alert=True)
                    raise ApplicationHandlerStop
            except ApplicationHandlerStop:
                raise
            except Exception:
                return

            # The closed-hours button must start a fresh partner login.
            # Do not require an already-active session here: the user has to
            # authenticate first, and telegram_partner_login_fix then checks
            # the exact night-worker whitelist after password verification.
            st = B.S.setdefault(uid, {})
            for key in ("partner_id","pending_partner_id","partner_phone","partner"):
                st.pop(key, None)
            st["mode"] = "p_phone"
            st["step"] = "partner_phone"
            try:
                await q.answer()
            except Exception:
                pass
            await q.message.reply_text("🌙 ورود همکاران شیفت شب\n\n📱 شماره موبایل اختصاصی همکار را وارد کنید:")
            raise ApplicationHandlerStop
        app.add_handler(CallbackQueryHandler(cb, pattern=r"^off:partner$"), group=-31001)
    except Exception:
        log.exception("night partner menu hotfix unavailable")

    B._partner_runtime_v31 = True
    log.info("REAL runtime: partner chat + night menu + admin bypass installed")
    return True
