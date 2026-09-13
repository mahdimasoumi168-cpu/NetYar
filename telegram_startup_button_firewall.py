"""Absolute Telegram startup router.

This module owns the language/citizenship entry flow. It is deliberately
installed at a very early handler group and stops the update so legacy
callback routers cannot consume the same button press.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

_LANG = {"fa", "en", "ar"}
_STATUS = {"foreign", "iranian"}


def _status_from_data(data):
    d = str(data or "").strip()
    if d in _STATUS:
        return d
    parts = d.split(":", 1)
    if len(parts) == 2 and parts[0] in {"startup", "st", "status", "citizen", "citizenship", "type", "user_type"} and parts[1] in _STATUS:
        return parts[1]
    return None


def _lang_from_data(data):
    d = str(data or "").strip()
    parts = d.split(":", 1)
    if len(parts) == 2 and parts[0] in {"lang", "language", "startup"} and parts[1] in _LANG:
        return parts[1]
    return None


async def _route_update(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q:
        return
    data = str(q.data or "").strip()
    lang = _lang_from_data(data)
    status = _status_from_data(data)
    if not lang and not status:
        return

    uid = q.from_user.id
    st = B.S.setdefault(uid, {})

    if lang:
        await q.answer()
        old = dict(st)
        B.S[uid] = {k: old[k] for k in ("partner_id", "partner_active", "admin", "phone") if k in old}
        B.S[uid]["lang"] = lang
        texts = {"fa": "آیا اتباع هستید یا ایرانی؟", "en": "Are you a foreign national or Iranian?", "ar": "هل أنت أجنبي أم إيراني؟"}
        labels = {
            "fa": ("🪪 اتباع هستم", "🇮🇷 ایرانی هستم"),
            "en": ("🪪 Foreign national", "🇮🇷 Iranian"),
            "ar": ("🪪 أجنبي", "🇮🇷 إيراني"),
        }[lang]
        await q.message.reply_text(texts[lang], reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(labels[0], callback_data="startup:foreign"),
            InlineKeyboardButton(labels[1], callback_data="startup:iranian"),
        ]]))
        raise ApplicationHandlerStop

    await q.answer()
    st["status"] = status
    st["citizenship"] = status
    st.pop("mode", None)
    current_lang = st.get("lang", "fa")
    if current_lang not in _LANG:
        current_lang = "fa"
    if status == "foreign":
        text = {"fa": "منوی خدمات کمک یار مهاجر 👇", "en": "Mohajer Helper services 👇", "ar": "قائمة خدمات المهاجرين 👇"}[current_lang]
    else:
        text = {"fa": "🇮🇷 منوی خدمات ایرانی 👇", "en": "🇮🇷 Iranian user menu 👇", "ar": "🇮🇷 قائمة المستخدم الإيراني 👇"}[current_lang]
    await q.message.reply_text(text, reply_markup=B.main(uid))
    raise ApplicationHandlerStop


def _text(update, context, B):
    if not update.message:
        return
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    if t in {"🪪 اتباع هستم", "🪪 Foreign national", "🪪 أجنبي"}:
        st = B.S.setdefault(uid, {})
        st["status"] = "foreign"
        st["citizenship"] = "foreign"
        st.pop("mode", None)
        return update.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))
    if t in {"🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"}:
        st = B.S.setdefault(uid, {})
        st["status"] = "iranian"
        st["citizenship"] = "iranian"
        st.pop("mode", None)
        return update.message.reply_text("🇮🇷 منوی خدمات ایرانی 👇", reply_markup=B.main(uid))


def install(app, B):
    if getattr(B, "_startup_button_firewall", False):
        return
    pattern = r"^(?:(?:lang|language|startup):(fa|en|ar)|(?:startup|st|status|citizen|citizenship|type|user_type):(foreign|iranian)|foreign|iranian)$"
    app.add_handler(CallbackQueryHandler(lambda u, c: _route_update(u, c, B), pattern=pattern), group=-1000000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)), group=-999999)
    B._startup_button_firewall = True
