"""Dedicated Iranian-user menu with trust and management access."""
import logging

log = logging.getLogger("netyar.iranian_menu")

FA_IRANIAN = ["🎫 پیگیری", "🛡️ اعتماد", "🔵 👥 پنل همکاران", "❌ انصراف"]
EN_IRANIAN = ["🎫 Tracking", "🛡️ Trust", "🔵 👥 Partner panel", "❌ Cancel"]
AR_IRANIAN = ["🎫 متابعة", "🛡️ الثقة", "🔵 👥 لوحة الشركاء", "❌ إلغاء"]
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
TRUST_IMAGE_URL = "https://trustseal.enamad.ir/logo.aspx?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"


def _lang(bot, uid):
    return bot.S.get(uid, {}).get("lang", "fa")


def _iranian_keyboard(bot, uid):
    lang = _lang(bot, uid)
    labels = EN_IRANIAN if lang == "en" else AR_IRANIAN if lang == "ar" else FA_IRANIAN
    return bot.kb([[labels[0]], [labels[1]], [labels[2]], [labels[3]]])


def _rubika_iranian_rows(rb, uid):
    lang = rb.STATE.get(str(uid), {}).get("lang", "fa")
    labels = EN_IRANIAN if lang == "en" else AR_IRANIAN if lang == "ar" else FA_IRANIAN
    return [[("1", labels[0])], [("2", labels[1])], [("3", labels[2])], [("0", labels[3])]]


def _trust_text(lang="fa"):
    if lang == "en":
        return "🛡️ Electronic Trust Symbol (eNAMAD)\n\nNetYar Mohajer\nDomain: netyarmohajer.sizpay.ir\nPhone: 03135674350\nEmail: netyaremohajer@gmail.com"
    if lang == "ar":
        return "🛡️ نماد الثقة الإلكتروني (eNAMAD)\n\nنت یار مهاجر\nالنطاق: netyarmohajer.sizpay.ir\nالهاتف: 03135674350\nالبريد: netyaremohajer@gmail.com"
    return "🛡️ نماد اعتماد الکترونیکی\n\n🏢 نام کسب‌وکار: نت یار مهاجر\n🔤 نام لاتین: NetYareMohajer\n🌐 دامنه: netyarmohajer.sizpay.ir\n☎️ تلفن: 03135674350\n📧 ایمیل: netyaremohajer@gmail.com"


def _trust_markup():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
        [InlineKeyboardButton("🌐 مشاهده وب‌سایت", url="https://netyarmohajer.sizpay.ir")],
    ])


def install():
    import bot
    if getattr(bot, "_iranian_menu_patch_installed", False):
        return

    old_statuscb = bot.statuscb

    async def statuscb_fixed(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        selected = str(q.data or "").split(":", 1)[-1]
        bot.S.setdefault(uid, {})["status"] = selected
        if selected == "iranian":
            lang = bot.S[uid].get("lang", "fa")
            return await q.message.reply_text(
                {"fa":"🇮🇷 منوی خدمات ایرانی 👇","en":"🇮🇷 Iranian services menu 👇","ar":"🇮🇷 قائمة الخدمات الإيرانية 👇"}.get(lang, "🇮🇷 منوی خدمات ایرانی 👇"),
                reply_markup=_iranian_keyboard(bot, uid),
            )
        return await old_statuscb(update, context)

    bot.statuscb = statuscb_fixed

    old_main = bot.main
    def main_colored(uid):
        return old_main(uid)
    bot.main = main_colored

    # Handle the Iranian trust button directly so it cannot be swallowed by
    # generic service dispatchers.
    try:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from telegram.ext import MessageHandler, filters
        async def trust_text_handler(update, context):
            if not update.message:
                return
            text = (update.message.text or "").strip()
            if text not in {"🛡️ اعتماد", "🛡 اعتماد", "🛡️ Trust", "🛡️ الثقة"}:
                return
            uid = update.effective_user.id
            lang = bot.S.get(uid, {}).get("lang", "fa")
            await update.message.reply_text(_trust_text(lang), reply_markup=_trust_markup(), disable_web_page_preview=True)
        bot.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trust_text_handler), group=-30000)
    except Exception:
        log.exception("Iranian trust handler could not install")

    try:
        import rubika_v2 as rb
        old_rb_handle = rb.handle
        def rb_handle_fixed(uid, chat, x, u):
            uid = str(uid); x = str(x or "").strip(); st = rb.STATE.setdefault(uid, {})
            step = st.get("step", "")
            if step == "citizenship" and x in {"2", "🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"}:
                st.update({"status":"iranian", "step":"iranian_menu"})
                return rb.send(chat, "🇮🇷 منوی خدمات ایرانی 👇", _rubika_iranian_rows(rb, uid))
            if step == "iranian_menu" or st.get("status") == "iranian":
                labels = FA_IRANIAN if st.get("lang", "fa") == "fa" else EN_IRANIAN if st.get("lang") == "en" else AR_IRANIAN
                if x in {"1", labels[0]}:
                    st["step"] = "menu"; return old_rb_handle(uid, chat, "🎫 پیگیری", u)
                if x in {"2", labels[1], "🛡 اعتماد", "🛡️ اعتماد", "🛡️ Trust", "🛡️ الثقة"}:
                    return rb.send(chat, "🛡️ نماد اعتماد الکترونیکی\nhttps://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH", _rubika_iranian_rows(rb, uid))
                if x in {"3", labels[2], "👥 پنل همکاران", "🔵 👥 پنل همکاران", "🔵 👥 Partner panel", "🔵 👥 لوحة الشركاء"}:
                    st["step"] = "menu"; return old_rb_handle(uid, chat, "👥 پنل همکاران", u)
                if x in {"0", labels[3], "❌ انصراف"}:
                    return rb.send(chat, "❌ عملیات لغو شد.", _rubika_iranian_rows(rb, uid))
            return old_rb_handle(uid, chat, x, u)
        rb.handle = rb_handle_fixed
    except Exception:
        log.exception("Rubika Iranian menu patch could not install")

    bot._iranian_menu_patch_installed = True
    log.info("Iranian menu / trust button patch installed")
