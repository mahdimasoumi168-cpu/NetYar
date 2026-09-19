"""Final hardening layer for the Iranian Telegram menu."""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.iranian_v38")


def _keyboard(B, uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 تست درگاه سیزپی — ۱۰۰٬۰۰۰ تومان", callback_data="sizpay:test")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="iranian:partner"),
         InlineKeyboardButton("🎫 پیگیری", callback_data="iranian:track")],
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="iranian:restart")],
    ])


def install(app, B):
    if getattr(B, "_iranian_menu_v38_installed", False):
        return True
    old_main = getattr(B, "main", None)
    def main(uid):
        if B.S.get(uid, {}).get("status") == "iranian":
            return _keyboard(B, uid)
        return old_main(uid) if callable(old_main) else _keyboard(B, uid)
    B.main = main

    async def show_menu(update, context):
        uid = int(update.effective_user.id); st = B.S.setdefault(uid, {})
        st["status"] = "iranian"; st["mode"] = None
        target = getattr(update, "message", None) or getattr(getattr(update, "callback_query", None), "message", None)
        if target:
            await target.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=_keyboard(B, uid))
        raise ApplicationHandlerStop

    async def citizenship_callback(update, context):
        q = update.callback_query
        if str(q.data or "") != "st:iranian": return
        await q.answer(); await show_menu(update, context)

    async def citizenship_text(update, context):
        text = (getattr(update.message, "text", "") or "").strip()
        if text in {"🇮🇷 ایرانی هستم", "ایرانی هستم", "🇮🇷 ایرانی"}:
            await show_menu(update, context)

    async def iranian_callback(update, context):
        q = update.callback_query; data = str(q.data or "")
        if not data.startswith("iranian:"): return
        act = data.split(":", 1)[1]; uid = int(q.from_user.id); st = B.S.setdefault(uid, {})
        await q.answer()
        if act == "back":
            st["status"] = "iranian"; st["mode"] = None
            await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=_keyboard(B, uid))
        elif act == "restart":
            st.clear(); st["lang"] = "fa"
            if hasattr(B, "start"): await B.start(update, context)
            else: await q.message.reply_text("🔄 لطفاً از دکمه شروع استفاده کنید.")
        elif act == "partner":
            st["mode"] = "p_phone"; await q.message.reply_text("📱 شماره همراه همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        elif act == "track":
            st["mode"] = "track"; await q.message.reply_text("🎫 کد پیگیری را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, citizenship_text), group=-10000003)
    app.add_handler(CallbackQueryHandler(citizenship_callback, pattern=r"^st:iranian$"), group=-10000002)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sizpay_menu_text), group=-10000000)
    app.add_handler(CallbackQueryHandler(iranian_callback, pattern=r"^iranian:(?:back|partner|track|restart)$"), group=-9999999)
    try:
        import telegram_universal_callback_owner_v46 as V46
        V46.install(app, B)
        log.info("Universal Telegram callback owner v48 installed from canonical runtime")
    except Exception:
        log.exception("Universal Telegram callback owner v48 unavailable")
    B._iranian_menu_v38_installed = True
    log.info("Iranian menu v38 installed without site link")
    return True
