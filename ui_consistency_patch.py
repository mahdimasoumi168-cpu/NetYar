"""UI consistency, language, support and admin compatibility patch.

This is intentionally isolated from the main bot flows so future UI changes do
not require rewriting the production handlers.
"""
import os
import logging

log = logging.getLogger("netyar.ui_consistency")
SUPPORT = "@Good_ok_2000"

FA_MAIN = [
    "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ",
    "🏛 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها",
    "📱 خدمات سیم کارت", "📝 آزمون غربالگری",
    "🎫 پیگیری", "💰 کیف پول من",
    "📞 تماس با ما", "📝 ثبت شکایت مشتریان",
    "🔵 👥 پنل همکاران",
]
EN_MAIN = [
    "🪪 FIDA non-in-person", "🖨 Printing",
    "🏛 Government access issue", "🎫 Card renewal tracking code",
    "📱 SIM services", "📝 Screening test",
    "🎫 Tracking", "💰 My wallet",
    "📞 Contact us", "📝 Customer complaint",
    "🔵 👥 Partner panel",
]
AR_MAIN = [
    "🪪 خدمة فيدا", "🖨 الطباعة",
    "🏛 مشكلة خدمات الحكومة", "🎫 رمز متابعة تجديد البطاقة",
    "📱 خدمات الشريحة", "📝 اختبار الفحص",
    "🎫 متابعة", "💰 محفظتي",
    "📞 اتصل بنا", "📝 شكوى العملاء",
    "🔵 👥 لوحة الشركاء",
]


def _lang(S, uid):
    return S.get(uid, {}).get("lang", "fa")


def _main_rows(bot, uid):
    lang = _lang(bot.S, uid)
    labels = EN_MAIN if lang == "en" else AR_MAIN if lang == "ar" else FA_MAIN
    return bot.kb([
        [labels[0], labels[1]],
        [labels[2], labels[3]],
        [labels[4], labels[5]],
        [labels[6], labels[7]],
        [labels[8], labels[9]],
        [labels[10]],
        [bot.CANCEL],
    ])


def _partner_rows(bot, uid=None):
    lang = _lang(bot.S, uid) if uid is not None else "fa"
    if lang == "en":
        rows = [["➕ Top up account", "🏛 Government access issue"], ["🔎 Tracking code", "📋 History"], ["💰 Balance"], ["🚪 Exit partner panel"]]
    elif lang == "ar":
        rows = [["➕ شحن الحساب", "🏛 مشكلة خدمات الحكومة"], ["🔎 رمز المتابعة", "📋 السجل"], ["💰 الرصيد"], ["🚪 خروج من لوحة الشركاء"]]
    else:
        rows = [["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🔎 پیگیری کد", "📋 سوابق"], ["💰 موجودی"], ["🚪 خروج از پنل"]]
    rows.append([bot.CANCEL])
    return bot.kb(rows)


def _normalize_main_text(x):
    aliases = {
        "🔵 👥 پنل همکاران": "👥 پنل همکاران",
        "🔵 👥 Partner panel": "👥 پنل همکاران",
        "🔵 👥 لوحة الشركاء": "👥 پنل همکاران",
        "📝 Screening test": "📝 آزمون غربالگری",
        "📝 اختبار الفحص": "📝 آزمون غربالگری",
        "🎫 Tracking": "🎫 پیگیری",
        "🎫 متابعة": "🎫 پیگیری",
        "📞 Contact us": "📞 تماس با ما",
        "📞 اتصل بنا": "📞 تماس با ما",
        "📝 Customer complaint": "📝 ثبت شکایت مشتریان",
        "📝 شكوى العملاء": "📝 ثبت شکایت مشتریان",
        "🏛 Government access issue": "🏛 حل مشکل ورود اتباع دولت من",
        "🏛 مشكلة خدمات الحكومة": "🏛 حل مشکل ورود اتباع دولت من",
        "🪪 FIDA non-in-person": "🪪 فیدای غیر حضوری",
        "🪪 خدمة فيدا": "🪪 فیدای غیر حضوری",
        "🖨 Printing": "🖨 خدمات چاپ",
        "🖨 الطباعة": "🖨 خدمات چاپ",
        "📱 SIM services": "📱 خدمات سیم کارت",
        "📱 خدمات الشريحة": "📱 خدمات سیم کارت",
        "💰 My wallet": "💰 کیف پول من",
        "💰 محفظتي": "💰 کیف پول من",
        "🎫 Card renewal tracking code": "🎫 کد رهگیری تمدید کارت‌ها",
        "🎫 رمز متابعة تجديد البطاقة": "🎫 کد رهگیری تمدید کارت‌ها",
    }
    return aliases.get(x, x)


def install():
    import bot
    if getattr(bot, "_ui_consistency_installed", False):
        return

    # Support two explicit admin variables in addition to the existing comma
    # separated ADMIN_IDS. Existing deployments remain unchanged.
    extra_admins = set()
    for key in ("ADMIN_ID_1", "ADMIN_ID_2", "ADMIN_IDS_1", "ADMIN_IDS_2"):
        value = os.getenv(key, "")
        extra_admins.update(x.strip() for x in value.replace(";", ",").split(",") if x.strip())
    bot.ADM.update(extra_admins)

    bot.main = lambda uid: _main_rows(bot, uid)
    bot.partner_kb = lambda lang="fa", _bot=bot: _partner_rows(_bot, None if lang == "fa" else None)

    old_langcb = bot.langcb
    async def langcb_fixed(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        selected = str(q.data or "").split(":", 1)[-1]
        if selected not in {"fa", "en", "ar"}:
            selected = "fa"
        bot.S[uid] = {"lang": selected}
        citizenship = {
            "fa": "آیا اتباع هستید یا ایرانی؟",
            "en": "Are you a foreign national or Iranian?",
            "ar": "هل أنت من الرعايا الأجانب أم إيراني؟",
        }[selected]
        buttons = {
            "fa": [[bot.InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"), bot.InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian")]],
            "en": [[bot.InlineKeyboardButton("🪪 Foreign national", callback_data="st:foreign"), bot.InlineKeyboardButton("🇮🇷 Iranian", callback_data="st:iranian")]],
            "ar": [[bot.InlineKeyboardButton("🪪 أجنبي", callback_data="st:foreign"), bot.InlineKeyboardButton("🇮🇷 إيراني", callback_data="st:iranian")]],
        }[selected]
        await q.message.reply_text(citizenship, reply_markup=bot.InlineKeyboardMarkup(buttons))

    old_statuscb = bot.statuscb
    async def statuscb_fixed(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        st = bot.S.setdefault(uid, {})
        st["status"] = str(q.data or "").split(":", 1)[-1]
        # Iranian users see the same service menu; do not show the old
        # "services unavailable" message.
        await q.message.reply_text(bot.L(uid, "منوی خدمات کمک یار مهاجر 👇", "Mohajer Helper services 👇", "خدمات مساعد المهاجر 👇"), reply_markup=bot.main(uid))

    bot.langcb = langcb_fixed
    bot.statuscb = statuscb_fixed

    old_ptext = bot.ptext
    async def ptext_fixed(update, context):
        uid = update.effective_user.id
        text = (update.message.text or "").strip()
        normalized = _normalize_main_text(text)
        if normalized in {"📞 تماس با ما", "📝 ثبت شکایت مشتریان"}:
            await update.message.reply_text(
                f"📞 پشتیبانی و تماس با ما:\n{SUPPORT}",
                reply_markup=bot.main(uid),
            )
            return
        if normalized != text:
            update.message.text = normalized
        # Keep the existing handler as the single source of service logic.
        return await old_ptext(update, context)

    bot.ptext = ptext_fixed
    bot._ui_consistency_installed = True
    log.info("UI consistency/language/support patch installed")
