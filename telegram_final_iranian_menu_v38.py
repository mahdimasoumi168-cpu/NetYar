"""Final hardening layer for the Iranian Telegram menu.

Loaded after every legacy layer. It overrides B.main for Iranian users and
adds high-priority text/callback handlers so the eNAMAD trust option cannot
disappear or be replaced by an older menu implementation.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.iranian_v38")
TRUST = "🛡 اعتماد"
TRUST_ALT = "🛡️ اعتماد"
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SITE_URL = "https://netyarmohajer.sizpay.ir"


def _keyboard(B, uid):
    rows = [
        ["🏛 خدمات ایرانی", TRUST],
        ["👥 پنل همکاران", "🎫 پیگیری"],
        ["🔄 شروع مجدد"],
    ]
    try:
        return B.kb(rows)
    except Exception:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏛 خدمات ایرانی", callback_data="iranian:services")],
            [InlineKeyboardButton(TRUST, callback_data="enamad:trust")],
            [InlineKeyboardButton("👥 پنل همکاران", callback_data="iranian:partner")],
            [InlineKeyboardButton("🎫 پیگیری", callback_data="iranian:track")],
            [InlineKeyboardButton("🔄 شروع مجدد", callback_data="iranian:restart")],
        ])


def _trust_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
        [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
        [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی", callback_data="iranian:back")],
    ])


def _trust_message():
    return (
        "🛡 نماد اعتماد الکترونیکی\n\n"
        "🏢 نام کسب‌وکار: نت یار مهاجر\n"
        "🔤 نام لاتین: NetYareMohajer\n"
        "🌐 دامنه: netyarmohajer.sizpay.ir\n"
        "☎️ تلفن: 03135674350\n"
        "📧 ایمیل: netyaremohajer@gmail.com"
    )


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
        uid = int(update.effective_user.id)
        st = B.S.setdefault(uid, {})
        st["status"] = "iranian"
        st["mode"] = None
        target = getattr(update, "message", None)
        if target is None:
            q = getattr(update, "callback_query", None)
            target = getattr(q, "message", None)
        if target:
            await target.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=_keyboard(B, uid))
        raise ApplicationHandlerStop

    async def citizenship_callback(update, context):
        q = update.callback_query
        if str(q.data or "") != "st:iranian":
            return
        await q.answer()
        await show_menu(update, context)

    async def citizenship_text(update, context):
        text = (getattr(update.message, "text", "") or "").strip()
        if text not in {"🇮🇷 ایرانی هستم", "ایرانی هستم", "🇮🇷 ایرانی"}:
            return
        await show_menu(update, context)

    async def trust_callback(update, context):
        q = update.callback_query
        if str(q.data or "") != "enamad:trust":
            return
        await q.answer()
        await q.message.reply_text(_trust_message(), reply_markup=_trust_markup(), disable_web_page_preview=True)
        raise ApplicationHandlerStop

    async def trust_text(update, context):
        text = (getattr(update.message, "text", "") or "").strip()
        if text not in {TRUST, TRUST_ALT}:
            return
        if B.S.get(int(update.effective_user.id), {}).get("status") != "iranian":
            return
        await update.message.reply_text(_trust_message(), reply_markup=_trust_markup(), disable_web_page_preview=True)
        raise ApplicationHandlerStop

    async def iranian_callback(update, context):
        q = update.callback_query
        data = str(q.data or "")
        if not data.startswith("iranian:"):
            return
        act = data.split(":", 1)[1]
        uid = int(q.from_user.id)
        st = B.S.setdefault(uid, {})
        await q.answer()
        if act in {"back", "services"}:
            st["status"] = "iranian"; st["mode"] = None
            await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=_keyboard(B, uid))
        elif act == "restart":
            st.clear(); st["lang"] = "fa"
            if hasattr(B, "start"):
                await B.start(update, context)
            else:
                await q.message.reply_text("🔄 لطفاً از دکمه شروع استفاده کنید.")
        elif act == "partner":
            st["mode"] = "p_phone"
            await q.message.reply_text("📱 شماره همراه همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        elif act == "track":
            st["mode"] = "track"
            await q.message.reply_text("🎫 کد پیگیری را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, citizenship_text), group=-10000003)
    app.add_handler(CallbackQueryHandler(citizenship_callback, pattern=r"^st:iranian$"), group=-10000002)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trust_text), group=-10000001)
    app.add_handler(CallbackQueryHandler(trust_callback, pattern=r"^enamad:trust$"), group=-10000000)
    app.add_handler(CallbackQueryHandler(iranian_callback, pattern=r"^iranian:(?:back|services|partner|track|restart)$"), group=-9999999)
    B._iranian_menu_v38_installed = True
    log.info("Iranian menu v38 installed: B.main + direct text/callback routing + eNAMAD trust")
    return True
