"""Telegram Persian-only start/restart and permanently available restart button."""
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

RESTART = "🔄 شروع مجدد"
USE_SERVICES = "🛎 استفاده از خدمات"


def _keyboard(rows=None):
    """Return a reply keyboard that always keeps restart available."""
    base = [list(r) for r in (rows or [])]
    # Avoid duplicate restart/service rows when an existing menu already has them.
    base = [r for r in base if RESTART not in r]
    base.append([RESTART])
    return ReplyKeyboardMarkup(
        base,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def _start_keyboard():
    return _keyboard([[USE_SERVICES]])


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
        reply_markup=_start_keyboard(),
    )


def install(app, B):
    if getattr(B, "_permanent_restart_v2", False):
        return

    # Patch the central keyboard factory so the restart button remains present
    # after ordinary menus, cancel menus, partner menus and service menus.
    old_kb = getattr(B, "kb", None)
    if callable(old_kb) and not getattr(B, "_restart_kb_wrapped", False):
        def persistent_kb(rows):
            base = [list(r) for r in (rows or [])]
            base = [r for r in base if RESTART not in r]
            base.append([RESTART])
            return old_kb(base)
        B.kb = persistent_kb
        B._restart_kb_wrapped = True

    old_start = B.start

    async def wrapped_start(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
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
            # Only use the original implementation as a safety fallback.
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
        await update.message.reply_text(
            "نوع کاربر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"),
                    InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian"),
                ]
            ]),
        )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, restart), group=-2000001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, use_services), group=-2000000)
    B._permanent_restart_v2 = True
