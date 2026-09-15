"""Telegram Persian-only start/restart and persistent restart button."""
from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

RESTART = "🔄 شروع مجدد"
USE_SERVICES = "🛎 استفاده از خدمات"


def _keyboard():
    # Both controls stay permanently available. The restart button is always
    # present below the service entry button.
    return ReplyKeyboardMarkup(
        [[USE_SERVICES], [RESTART]],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def _clear_flow(st):
    # Language is no longer a user choice: NetYar is Persian-only.
    # Preserve an authenticated partner session when restarting.
    keep = {
        k: st[k]
        for k in ("partner_id", "partner_active", "partner_phone", "partner_username", "status")
        if k in st
    }
    st.clear()
    st.update(keep)
    st["lang"] = "fa"
    st["mode"] = None


async def _show_persian_start(update, context, B):
    st = B.S.setdefault(update.effective_user.id, {})
    st["lang"] = "fa"
    st["mode"] = None
    await update.effective_message.reply_text(
        "سلام و خوش آمدید 🌷\n\n"
        "به «کمک یار مهاجر» خوش آمدید.\n"
        "برای دریافت خدمات، روی دکمه زیر بزنید.",
        reply_markup=_keyboard(),
    )


def install(app, B):
    if getattr(B, "_permanent_restart_v2", False):
        return

    old_start = B.start

    async def wrapped_start(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        # Do not let /start or an internal restart erase a partner login.
        partner_keep = {
            k: st[k]
            for k in ("partner_id", "partner_active", "partner_phone", "partner_username", "status")
            if k in st
        }
        st.clear()
        st.update(partner_keep)
        st["lang"] = "fa"
        st["mode"] = None
        try:
            await _show_persian_start(update, context, B)
        except Exception:
            # Fall back to the original start only if the custom Persian start
            # cannot be rendered; never break the Telegram receiver.
            await old_start(update, context)
        return None

    B.start = wrapped_start
    B.restart_keyboard = _keyboard

    async def restart(update, context):
        if not update.message:
            return
        if (update.message.text or "").strip() not in {RESTART, "شروع مجدد"}:
            return
        st = B.S.setdefault(update.effective_user.id, {})
        _clear_flow(st)
        await _show_persian_start(update, context, B)
        raise ApplicationHandlerStop

    async def use_services(update, context):
        if not update.message:
            return
        if (update.message.text or "").strip() != USE_SERVICES:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        st["lang"] = "fa"
        st["mode"] = None
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await update.message.reply_text(
            "نوع کاربر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"),
                    InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian"),
                ]
            ]),
            # Keep the persistent reply keyboard visible below the conversation.
        )
        raise ApplicationHandlerStop

    # Highest priority: these two controls must win over generic text handlers.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, restart), group=-2000001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, use_services), group=-2000000)
    B._permanent_restart_v2 = True
