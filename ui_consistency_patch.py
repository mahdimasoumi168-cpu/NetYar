"""UI consistency, language, support and admin compatibility patch."""
import os
import logging

log = logging.getLogger("netyar.ui_consistency")
SUPPORT = "@Good_ok_2000"

FA_MAIN = ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ", "🏛 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها", "📱 خدمات سیم کارت", "📝 آزمون غربالگری", "🎫 پیگیری", "💰 کیف پول من", "📞 تماس با ما", "📝 ثبت شکایت مشتریان", "🔵 👥 پنل همکاران"]
EN_MAIN = ["🪪 FIDA non-in-person", "🖨 Printing", "🏛 Government access issue", "🎫 Card renewal tracking code", "📱 SIM services", "📝 Screening test", "🎫 Tracking", "💰 My wallet", "📞 Contact us", "📝 Customer complaint", "🔵 👥 Partner panel"]
AR_MAIN = ["🪪 خدمة فيدا", "🖨 الطباعة", "🏛 مشكلة خدمات الحكومة", "🎫 رمز متابعة تجديد البطاقة", "📱 خدمات الشريحة", "📝 اختبار الفحص", "🎫 متابعة", "💰 محفظتي", "📞 اتصل بنا", "📝 شكوى العملاء", "🔵 👥 لوحة الشركاء"]


def _lang(S, uid):
    return S.get(uid, {}).get("lang", "fa")


def _main_rows(bot, uid):
    labels = EN_MAIN if _lang(bot.S, uid) == "en" else AR_MAIN if _lang(bot.S, uid) == "ar" else FA_MAIN
    return bot.kb([[labels[0], labels[1]], [labels[2], labels[3]], [labels[4], labels[5]], [labels[6], labels[7]], [labels[8], labels[9]], [labels[10]], [bot.CANCEL]])


def _partner_rows(bot, uid=None):
    lang = _lang(bot.S, uid if uid is not None else getattr(bot, "_ui_current_uid", None))
    if lang == "en":
        rows = [["➕ Top up account", "🏛 Government access issue"], ["🔎 Tracking code", "📋 History"], ["💰 Balance"], ["🚪 Exit partner panel"]]
    elif lang == "ar":
        rows = [["➕ شحن الحساب", "🏛 مشكلة خدمات الحكومة"], ["🔎 رمز المتابعة", "📋 السجل"], ["💰 الرصيد"], ["🚪 خروج من لوحة الشركاء"]]
    else:
        rows = [["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🔎 پیگیری کد", "📋 سوابق"], ["💰 موجودی"], ["🚪 خروج از پنل"]]
    rows.append([bot.CANCEL])
    return bot.kb(rows)


def _normalize_main_text(x):
    return {
        "🔵 👥 پنل همکاران": "👥 پنل همکاران", "🔵 👥 Partner panel": "👥 پنل همکاران", "🔵 👥 لوحة الشركاء": "👥 پنل همکاران",
        "📝 Screening test": "📝 آزمون غربالگری", "📝 اختبار الفحص": "📝 آزمون غربالگری",
        "🎫 Tracking": "🎫 پیگیری", "🎫 متابعة": "🎫 پیگیری",
        "📞 Contact us": "📞 تماس با ما", "📞 اتصل بنا": "📞 تماس با ما",
        "📝 Customer complaint": "📝 ثبت شکایت مشتریان", "📝 شكوى العملاء": "📝 ثبت شکایت مشتریان",
        "🏛 Government access issue": "🏛 حل مشکل ورود اتباع دولت من", "🏛 مشكلة خدمات الحكومة": "🏛 حل مشکل ورود اتباع دولت من",
        "🪪 FIDA non-in-person": "🪪 فیدای غیر حضوری", "🪪 خدمة فيدا": "🪪 فیدای غیر حضوری",
        "🖨 Printing": "🖨 خدمات چاپ", "🖨 الطباعة": "🖨 خدمات چاپ",
        "📱 SIM services": "📱 خدمات سیم کارت", "📱 خدمات الشريحة": "📱 خدمات سیم کارت",
        "💰 My wallet": "💰 کیف پول من", "💰 محفظتي": "💰 کیف پول من",
        "🎫 Card renewal tracking code": "🎫 کد رهگیری تمدید کارت‌ها", "🎫 رمز متابعة تجديد البطاقة": "🎫 کد رهگیری تمدید کارت‌ها",
    }.get(x, x)


def _rubika_main_rows(rb, uid):
    lang = rb.STATE.get(str(uid), {}).get("lang", "fa")
    labels = EN_MAIN if lang == "en" else AR_MAIN if lang == "ar" else FA_MAIN
    return [[(str(i + 1), labels[i]) for i in range(0, 2)], [(str(i + 1), labels[i]) for i in range(2, 4)], [(str(i + 1), labels[i]) for i in range(4, 6)], [(str(i + 1), labels[i]) for i in range(6, 8)], [(str(i + 1), labels[i]) for i in range(8, 10)], [("11", labels[10])], [("0", rb.CANCEL)]]


def install():
    import bot
    if getattr(bot, "_ui_consistency_installed", False):
        return

    extra_admins = set()
    for key in ("ADMIN_ID_1", "ADMIN_ID_2", "ADMIN_IDS_1", "ADMIN_IDS_2"):
        value = os.getenv(key, "")
        extra_admins.update(x.strip() for x in value.replace(";", ",").split(",") if x.strip())
    bot.ADM.update(extra_admins)
    bot.main = lambda uid: _main_rows(bot, uid)
    bot._ui_current_uid = None
    bot.partner_kb = lambda lang="fa", _bot=bot: _partner_rows(_bot)

    async def langcb_fixed(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        selected = str(q.data or "").split(":", 1)[-1]
        selected = selected if selected in {"fa", "en", "ar"} else "fa"
        bot.S[uid] = {"lang": selected}
        citizenship = {"fa": "آیا اتباع هستید یا ایرانی؟", "en": "Are you a foreign national or Iranian?", "ar": "هل أنت من الرعايا الأجانب أم إيراني؟"}[selected]
        buttons = {
            "fa": [[bot.InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"), bot.InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian")]],
            "en": [[bot.InlineKeyboardButton("🪪 Foreign national", callback_data="st:foreign"), bot.InlineKeyboardButton("🇮🇷 Iranian", callback_data="st:iranian")]],
            "ar": [[bot.InlineKeyboardButton("🪪 أجنبي", callback_data="st:foreign"), bot.InlineKeyboardButton("🇮🇷 إيراني", callback_data="st:iranian")]],
        }[selected]
        await q.message.reply_text(citizenship, reply_markup=bot.InlineKeyboardMarkup(buttons))

    async def statuscb_fixed(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        bot.S.setdefault(uid, {})["status"] = str(q.data or "").split(":", 1)[-1]
        msg = {"fa": "منوی خدمات کمک یار مهاجر 👇", "en": "Mohajer Helper services 👇", "ar": "خدمات مساعد المهاجر 👇"}.get(bot.S[uid].get("lang", "fa"), "منوی خدمات کمک یار مهاجر 👇")
        await q.message.reply_text(msg, reply_markup=bot.main(uid))

    bot.langcb = langcb_fixed
    bot.statuscb = statuscb_fixed

    old_ptext = bot.ptext
    async def ptext_fixed(update, context):
        uid = update.effective_user.id
        bot._ui_current_uid = uid
        text = (update.message.text or "").strip()
        normalized = _normalize_main_text(text)
        if normalized in {"📞 تماس با ما", "📝 ثبت شکایت مشتریان"}:
            await update.message.reply_text(f"📞 پشتیبانی و تماس با ما:\n{SUPPORT}", reply_markup=bot.main(uid))
            return
        if normalized != text:
            import copy
            proxy_update = copy.copy(update)
            proxy_message = copy.copy(update.message)
            proxy_message.text = normalized
            proxy_update.message = proxy_message
            update = proxy_update
        return await old_ptext(update, context)

    bot.ptext = ptext_fixed

    # Rubika uses its own state machine; keep the same language/menu contract.
    try:
        import rubika_v2 as rb
        rb.main_rows = lambda uid: _rubika_main_rows(rb, uid)
        rb.partner_rows = lambda: _rubika_partner_rows(rb)
        rb._ui_last_uid = None
        old_rb_handle = rb.handle

        def _rubika_partner_rows(rb):
            uid = getattr(rb, "_ui_last_uid", None)
            lang = rb.STATE.get(str(uid), {}).get("lang", "fa")
            if lang == "en": rows = [[("1", "➕ Top up account"), ("2", "🏛 Government access issue")], [("3", "🔎 Tracking code"), ("4", "📋 History")], [("5", "💰 Balance")], [("6", "🚪 Exit partner panel")], [("0", rb.CANCEL)]]
            elif lang == "ar": rows = [[("1", "➕ شحن الحساب"), ("2", "🏛 مشكلة خدمات الحكومة")], [("3", "🔎 رمز المتابعة"), ("4", "📋 السجل")], [("5", "💰 الرصيد")], [("6", "🚪 خروج من لوحة الشركاء")], [("0", rb.CANCEL)]]
            else: rows = [[("1", "➕ شارژ حساب"), ("2", "🏛 حل مشکل سامانه دولت من")], [("3", "🔎 پیگیری کد"), ("4", "📋 سوابق")], [("5", "💰 موجودی")], [("6", "🚪 خروج از پنل")], [("0", rb.CANCEL)]]
            return rows

        def rb_handle_fixed(uid, chat, x, u):
            uid = str(uid)
            rb._ui_last_uid = uid
            x = str(x or "").strip()
            st = rb.STATE.setdefault(uid, {})
            step = st.get("step", "")
            if step == "language" and x in {"1", "🇮🇷 فارسی", "2", "🇬🇧 English", "3", "🇸🇦 العربية"}:
                selected = {"1": "fa", "🇮🇷 فارسی": "fa", "2": "en", "🇬🇧 English": "en", "3": "ar", "🇸🇦 العربية": "ar"}[x]
                st["lang"] = selected; st["step"] = "citizenship"
                texts = {"fa": "آیا اتباع هستید یا ایرانی؟", "en": "Are you a foreign national or Iranian?", "ar": "هل أنت من الرعايا الأجانب أم إيراني؟"}
                labels = {"fa": [("1", "🪪 اتباع هستم"), ("2", "🇮🇷 ایرانی هستم")], "en": [("1", "🪪 Foreign national"), ("2", "🇮🇷 Iranian")], "ar": [("1", "🪪 أجنبي"), ("2", "🇮🇷 إيراني")]}[selected]
                return rb.send(chat, texts[selected], [[labels[0]], [labels[1]]])
            if step == "citizenship" and x in {"1", "2", "🪪 اتباع هستم", "🪪 Foreign national", "🪪 أجنبي", "🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"}:
                st["step"] = "menu"
                return rb.send(chat, {"fa": "منوی خدمات کمک یار مهاجر 👇", "en": "Mohajer Helper services 👇", "ar": "خدمات مساعد المهاجر 👇"}.get(st.get("lang", "fa"), "منوی خدمات کمک یار مهاجر 👇"), rb.main_rows(uid))
            if step == "menu":
                aliases = {"🔵 👥 پنل همکاران": "👥 پنل همکاران", "🔵 👥 Partner panel": "👥 پنل همکاران", "🔵 👥 لوحة الشركاء": "👥 پنل همکاران", "📞 Contact us": "📞 تماس با ما", "📞 اتصل بنا": "📞 تماس با ما"}
                x = aliases.get(x, x)
                if x in {"📞 تماس با ما"}:
                    lang = st.get("lang", "fa")
                    msg = {"fa": f"📞 پشتیبانی و تماس با ما:\n{SUPPORT}", "en": f"📞 Support:\n{SUPPORT}", "ar": f"📞 الدعم:\n{SUPPORT}"}[lang]
                    return rb.send(chat, msg, rb.main_rows(uid))
            return old_rb_handle(uid, chat, x, u)

        rb.handle = rb_handle_fixed
    except Exception:
        log.exception("Rubika UI patch could not install")

    bot._ui_consistency_installed = True
    log.info("UI consistency/language/support/admin patch installed")
