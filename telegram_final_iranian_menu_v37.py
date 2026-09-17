"""Final Telegram Iranian-menu router.

This layer is intentionally installed last. It owns the st:iranian callback
so legacy handlers cannot replace the Iranian menu with the old unavailable
message. It also exposes the eNAMAD trust button directly in that menu.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.iranian_v37")
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SITE_URL = "https://netyarmohajer.sizpay.ir"
TRUST = "🛡 اعتماد"


def _menu(B, uid):
    # Inline menu is authoritative: it cannot be hidden by Telegram's reply
    # keyboard state and every button has an explicit callback.
    rows = [
        [InlineKeyboardButton("🏛 خدمات ایرانی", callback_data="iranian:services")],
        [InlineKeyboardButton(TRUST, callback_data="enamad:trust")],
        [InlineKeyboardButton("👥 پنل همکاران", callback_data="iranian:partner")],
        [InlineKeyboardButton("🎫 پیگیری", callback_data="iranian:track")],
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="iranian:restart")],
    ]
    return InlineKeyboardMarkup(rows)


def install(app, B):
    if getattr(B, "_iranian_menu_v37_installed", False):
        return True

    async def iranian(update, context):
        q = getattr(update, "callback_query", None)
        if not q or str(q.data or "") != "st:iranian":
            return
        uid = q.from_user.id
        await q.answer()
        st = B.S.setdefault(uid, {})
        st["status"] = "iranian"
        st["mode"] = None
        lang = st.get("lang", "fa")
        text = {
            "fa": "🇮🇷 منوی ایرانی\n\nگزینه موردنظر را انتخاب کنید:",
            "en": "🇮🇷 Iranian menu\n\nPlease choose an option:",
            "ar": "🇮🇷 قائمة الإيرانيين\n\nاختر أحد الخيارات:",
        }.get(lang, "🇮🇷 منوی ایرانی\n\nگزینه موردنظر را انتخاب کنید:")
        await q.message.reply_text(text, reply_markup=_menu(B, uid))
        raise ApplicationHandlerStop

    async def trust(update, context):
        q = getattr(update, "callback_query", None)
        if not q or str(q.data or "") != "enamad:trust":
            return
        await q.answer()
        await q.message.reply_text(
            "🛡 نماد اعتماد الکترونیکی\n\n"
            "🏢 نام کسب‌وکار: نت یار مهاجر\n"
            "🔤 نام لاتین: NetYareMohajer\n"
            "🌐 دامنه: netyarmohajer.sizpay.ir\n"
            "☎️ تلفن: 03135674350\n"
            "📧 ایمیل: netyaremohajer@gmail.com",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
                [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
                [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی", callback_data="iranian:back")],
            ]),
            disable_web_page_preview=True,
        )
        raise ApplicationHandlerStop

    async def actions(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        data = str(q.data or "")
        if not data.startswith("iranian:"):
            return
        act = data.split(":", 1)[1]
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        await q.answer()
        if act in {"back", "services"}:
            st["status"] = "iranian"
            st["mode"] = None
            await q.message.reply_text("🇮🇷 منوی ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=_menu(B, uid))
            raise ApplicationHandlerStop
        if act == "restart":
            st.clear()
            st["lang"] = "fa"
            await q.message.reply_text("🔄 لطفاً از دکمه شروع استفاده کنید.")
            raise ApplicationHandlerStop
        if act == "partner":
            st["mode"] = "p_phone"
            await q.message.reply_text("📱 شماره همراه همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop
        if act == "track":
            st["mode"] = "track"
            await q.message.reply_text("🎫 کد پیگیری را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop

    async def trust_text(update, context):
        if not update.message:
            return
        if (update.message.text or "").strip() != TRUST:
            return
        await update.message.reply_text(
            "🛡 نماد اعتماد الکترونیکی\n\n"
            "🏢 نام کسب‌وکار: نت یار مهاجر\n"
            "🌐 دامنه: netyarmohajer.sizpay.ir",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
                [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
            ]),
            disable_web_page_preview=True,
        )
        raise ApplicationHandlerStop

    # Extremely early groups prevent old st:iranian/ir:* catch-alls from
    # sending the obsolete "services unavailable" response.
    app.add_handler(CallbackQueryHandler(iranian, pattern=r"^st:iranian$"), group=-10000001)
    app.add_handler(CallbackQueryHandler(trust, pattern=r"^enamad:trust$"), group=-10000000)
    app.add_handler(CallbackQueryHandler(actions, pattern=r"^iranian:(?:back|services|partner|track|restart)$"), group=-9999999)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trust_text), group=-9999998)
    B._iranian_menu_v37_installed = True
    log.info("Final Iranian menu v37 installed: trust button forced into Iranian menu")
    return True
