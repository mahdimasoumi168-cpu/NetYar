"""Dedicated Iranian-user menu and consistent colored menu labels."""
import logging

log = logging.getLogger("netyar.iranian_menu")

FA_IRANIAN = ["🎫 پیگیری", "🔵 👥 پنل همکاران", "🛡 اعتماد", "❌ انصراف"]
EN_IRANIAN = ["🎫 Tracking", "🔵 👥 Partner panel", "🛡 Trust", "❌ Cancel"]
AR_IRANIAN = ["🎫 متابعة", "🔵 👥 لوحة الشركاء", "🛡 اعتماد", "❌ إلغاء"]


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
            msg = {
                "fa": "🇮🇷 منوی خدمات ایرانی 👇",
                "en": "🇮🇷 Iranian services menu 👇",
                "ar": "🇮🇷 قائمة الخدمات الإيرانية 👇",
            }.get(lang, "🇮🇷 منوی خدمات ایرانی 👇")
            return await q.message.reply_text(msg, reply_markup=_iranian_keyboard(bot, uid))
        return await old_statuscb(update, context)

    bot.statuscb = statuscb_fixed

    old_main = bot.main

    def main_colored(uid):
        markup = old_main(uid)
        try:
            rows = []
            for row in getattr(markup, "inline_keyboard", []) or []:
                labels = []
                for item in row:
                    labels.append(getattr(item, "text", str(item)))
                if labels:
                    rows.append(labels)
            if bot.admin(uid):
                rows = [r for r in rows if "❌ انصراف" not in r]
                rows.append(["🔵 🛠 پنل مدیریت بات"])
                rows.append(["❌ انصراف"])
            return bot.kb(rows)
        except Exception:
            return markup

    bot.main = main_colored

    try:
        import rubika_v2 as rb
        old_rb_handle = rb.handle

        def rb_handle_fixed(uid, chat, x, u):
            uid = str(uid)
            x = str(x or "").strip()
            st = rb.STATE.setdefault(uid, {})
            step = st.get("step", "")
            if step == "citizenship" and x in {
                "2", "🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"
            }:
                st["status"] = "iranian"
                st["step"] = "iranian_menu"
                lang = st.get("lang", "fa")
                msg = {
                    "fa": "🇮🇷 منوی خدمات ایرانی 👇",
                    "en": "🇮🇷 Iranian services menu 👇",
                    "ar": "🇮🇷 قائمة الخدمات الإيرانية 👇",
                }.get(lang, "🇮🇷 منوی خدمات ایرانی 👇")
                return rb.send(chat, msg, _rubika_iranian_rows(rb, uid))
            if step == "iranian_menu" or st.get("status") == "iranian":
                labels = FA_IRANIAN if st.get("lang", "fa") == "fa" else EN_IRANIAN if st.get("lang") == "en" else AR_IRANIAN
                if x in {"1", labels[0]}:
                    st["step"] = "menu"
                    return old_rb_handle(uid, chat, "🎫 پیگیری", u)
                if x in {"2", labels[1], "👥 پنل همکاران", "🔵 👥 پنل همکاران", "🔵 👥 Partner panel", "🔵 👥 لوحة الشركاء"}:
                    st["step"] = "menu"
                    return old_rb_handle(uid, chat, "👥 پنل همکاران", u)
                if x in {"3", labels[2], "🛡 اعتماد", "🛡 Trust", "🛡 اعتماد"}:
                    st["step"] = "iranian_menu"
                    return rb.send(chat, "🛡 نماد اعتماد الکترونیکی\n\nبرای مشاهده و بررسی نماد اعتماد، از گزینه اعتماد در منو استفاده کنید.", _rubika_iranian_rows(rb, uid))
                if x in {"0", labels[3], "❌ انصراف"}:
                    st["status"] = "iranian"
                    st["step"] = "iranian_menu"
                    return rb.send(chat, "❌ عملیات لغو شد.", _rubika_iranian_rows(rb, uid))
            return old_rb_handle(uid, chat, x, u)

        rb.handle = rb_handle_fixed
        rb.iranian_rows = lambda uid: _rubika_iranian_rows(rb, uid)
    except Exception:
        log.exception("Rubika Iranian menu patch could not install")

    bot._iranian_menu_patch_installed = True
    log.info("Iranian menu / colored management button patch installed")
