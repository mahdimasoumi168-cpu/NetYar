"""Deterministic Telegram startup router.

Startup language/citizenship callbacks use a dedicated namespace so they cannot
collide with legacy callback routers elsewhere in the project.
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import TypeHandler, CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

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
    if len(parts) == 2 and parts[0] in {"lang", "language", "startup"}:
        value = parts[1]
        if value in _LANG:
            return value
    return None


async def _route_update(update, context, B):
    q = update.callback_query
    if not q:
        return
    data = str(q.data or "").strip()
    lang = _lang_from_data(data)
    status = _status_from_data(data)
    if not lang and not status:
        return

    await q.answer()
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})

    if lang:
        old = dict(st)
        B.S[uid] = {k: old[k] for k in ("partner_id", "partner_active", "admin", "phone") if k in old}
        B.S[uid]["lang"] = lang
        texts = {
            "fa": "آیا اتباع هستید یا ایرانی؟",
            "en": "Are you a foreign national or Iranian?",
            "ar": "هل أنت أجنبي أم إيراني؟",
        }
        labels = {
            "fa": ("🪪 اتباع هستم", "🇮🇷 ایرانی هستم"),
            "en": ("🪪 Foreign national", "🇮🇷 Iranian"),
            "ar": ("🪪 أجنبي", "🇮🇷 إيراني"),
        }[lang]
        await q.message.reply_text(
            texts[lang],
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(labels[0], callback_data="startup:foreign"),
                InlineKeyboardButton(labels[1], callback_data="startup:iranian"),
            ]]),
        )
        raise ApplicationHandlerStop

    st["status"] = status
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


async def _status(update, context, B):
    if update.callback_query and _status_from_data(update.callback_query.data):
        await _route_update(update, context, B)


async def _lang(update, context, B):
    if update.callback_query and _lang_from_data(update.callback_query.data):
        await _route_update(update, context, B)


async def _text(update, context, B):
    if not update.message:
        return
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    if t in {"🪪 اتباع هستم", "🪪 Foreign national", "🪪 أجنبي"}:
        st = B.S.setdefault(uid, {})
        st["status"] = "foreign"
        st.pop("mode", None)
        await update.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    if t in {"🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"}:
        st = B.S.setdefault(uid, {})
        st["status"] = "iranian"
        st.pop("mode", None)
        await update.message.reply_text("🇮🇷 منوی خدمات ایرانی 👇", reply_markup=B.main(uid))
        raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_startup_button_firewall", False):
        return
    app.add_handler(TypeHandler(Update, lambda u, c: _route_update(u, c, B)), group=-300)
    app.add_handler(CallbackQueryHandler(lambda u, c: _lang(u, c, B), pattern=r"^(?:lang|language|startup):(fa|en|ar)$"), group=-200)
    app.add_handler(CallbackQueryHandler(lambda u, c: _status(u, c, B), pattern=r"^(?:(?:startup|st|status|citizen|citizenship|type|user_type):(foreign|iranian)|foreign|iranian)$"), group=-199)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)), group=-198)
    B._startup_button_firewall = True
