"""Dedicated Iranian-user menu and consistent colored menu labels."""
import logging

log = logging.getLogger("netyar.iranian_menu")

FA_IRANIAN = ["🎫 پیگیری", "🔵 👥 پنل همکاران", "❌ انصراف"]
EN_IRANIAN = ["🎫 Tracking", "🔵 👥 Partner panel", "❌ Cancel"]
AR_IRANIAN = ["🎫 متابعة", "🔵 👥 لوحة الشركاء", "❌ إلغاء"]


def _lang(bot, uid):
    return bot.S.get(uid, {}).get("lang", "fa")


def _iranian_keyboard(bot, uid):
    lang = _lang(bot, uid)
    labels = EN_IRANIAN if lang == "en" else AR_IRANIAN if lang == "ar" else FA_IRANIAN
    return bot.kb([[labels[0]], [labels[1]], [labels[2]]])


def _rubika_iranian_rows(rb, uid):
    lang = rb.STATE.get(str(uid), {}).get("lang", "fa")
    if lang == "en":
        labels = EN_IRANIAN
    elif lang == "ar":
        labels = AR_IRANIAN
    else:
        labels = FA_IRANIAN
    return [[("1", labels[0])], [("2", labels[1])], [("0", labels[2])]]


def install():
    import bot
    if getattr(bot, "_iranian_menu_patch_installed", False):
        return

    # Telegram: Iranian users get only tracking, partner panel and cancel.
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

    # Keep the management option visually blue wherever the main menu is built.
    old_main = bot.main

    def main_colored(uid):
        markup = old_main(uid)
        try:
            # Replace only the management label; preserve every other menu item/order.
            for row in markup.keyboard:
                for i, item in enumerate(row):
                    text = getattr(item, "text", str(item))
                    if text in {"🛠 پنل مدیریت بات", "پنل مدیریت بات", "🔵 🛠 پنل مدیریت بات"}:
                        row[i] = "🔵 🛠 پنل مدیریت بات"
        except Exception:
            pass
        return markup

    bot.main = main_colored

    # Rubika has a separate state machine; intercept the Iranian branch before
    # the general service menu can consume numeric choices.
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
                    # Reuse the existing tracking handler through the normal flow.
                    return old_rb_handle(uid, chat, "🎫 پیگیری", u)
                if x in {"2", labels[1], "👥 پنل همکاران", "🔵 👥 پنل همکاران", "🔵 👥 Partner panel", "🔵 👥 لوحة الشركاء"}:
                    st["step"] = "menu"
                    return old_rb_handle(uid, chat, "👥 پنل همکاران", u)
                if x in {"0", labels[2], "❌ انصراف"}:
                    st["status"] = "iranian"
                    st["step"] = "menu"
                    return rb.send(chat, "❌ عملیات لغو شد.", _rubika_iranian_rows(rb, uid))
            return old_rb_handle(uid, chat, x, u)

        rb.handle = rb_handle_fixed
        rb.iranian_rows = lambda uid: _rubika_iranian_rows(rb, uid)
    except Exception:
        log.exception("Rubika Iranian menu patch could not install")

    bot._iranian_menu_patch_installed = True
    log.info("Iranian menu / colored management button patch installed")
