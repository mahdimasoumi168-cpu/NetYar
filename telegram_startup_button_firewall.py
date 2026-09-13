"""Final high-priority Telegram startup/citizenship button router.

Handles both current and legacy callback-data variants plus reply-keyboard text,
then stops further handlers so duplicate/competing routers cannot consume them.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

_LANG = {"fa", "en", "ar"}
_STATUS = {"foreign", "iranian"}

def _status_from_data(data):
    d = str(data or "").strip()
    if d in {"foreign", "iranian"}: return d
    parts = d.split(":")
    if len(parts) == 2 and parts[0] in {"st", "status", "citizen", "citizenship", "type", "user_type"} and parts[1] in _STATUS:
        return parts[1]
    return None

def _lang_from_data(data):
    d = str(data or "").strip()
    parts = d.split(":")
    if len(parts) == 2 and parts[0] in {"lang", "language"} and parts[1] in _LANG:
        return parts[1]
    return None

async def _status(update, context, B):
    q = update.callback_query
    if not q: return
    status = _status_from_data(q.data)
    if not status: return
    await q.answer()
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})
    st["status"] = status
    st.pop("mode", None)
    lang = st.get("lang", "fa")
    if lang not in _LANG: lang = "fa"
    if status == "foreign":
        text = {"fa":"منوی خدمات کمک یار مهاجر 👇", "en":"Mohajer Helper services 👇", "ar":"قائمة خدمات المهاجرين 👇"}[lang]
    else:
        text = {"fa":"🇮🇷 منوی خدمات ایرانی 👇", "en":"🇮🇷 Iranian user menu 👇", "ar":"🇮🇷 قائمة المستخدم الإيراني 👇"}[lang]
    await q.message.reply_text(text, reply_markup=B.main(uid))
    raise ApplicationHandlerStop

async def _lang(update, context, B):
    q = update.callback_query
    if not q: return
    lang = _lang_from_data(q.data)
    if not lang: return
    await q.answer()
    uid = q.from_user.id
    old = B.S.get(uid, {})
    B.S[uid] = {k: old[k] for k in ("partner_id", "partner_active", "admin", "phone") if k in old}
    B.S[uid]["lang"] = lang
    texts = {"fa":"آیا اتباع هستید یا ایرانی؟", "en":"Are you a foreign national or Iranian?", "ar":"هل أنت أجنبي أم إيراني؟"}
    labels = {"fa":("🪪 اتباع هستم","🇮🇷 ایرانی هستم"), "en":("🪪 Foreign national","🇮🇷 Iranian"), "ar":("🪪 أجنبي","🇮🇷 إيراني")}[lang]
    await q.message.reply_text(texts[lang], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(labels[0], callback_data="st:foreign"), InlineKeyboardButton(labels[1], callback_data="st:iranian")]]))
    raise ApplicationHandlerStop

async def _text(update, context, B):
    if not update.message: return
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    if t in {"🪪 اتباع هستم", "🪪 Foreign national", "🪪 أجنبي"}:
        st = B.S.setdefault(uid, {})
        st["status"] = "foreign"; st.pop("mode", None)
        await update.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    if t in {"🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"}:
        st = B.S.setdefault(uid, {})
        st["status"] = "iranian"; st.pop("mode", None)
        await update.message.reply_text("🇮🇷 منوی خدمات ایرانی 👇", reply_markup=B.main(uid))
        raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, "_startup_button_firewall", False): return
    app.add_handler(CallbackQueryHandler(lambda u,c: _lang(u,c,B), pattern=r"^(?:lang|language):(fa|en|ar)$"), group=-200)
    app.add_handler(CallbackQueryHandler(lambda u,c: _status(u,c,B), pattern=r"^(?:(?:st|status|citizen|citizenship|type|user_type):(foreign|iranian)|foreign|iranian)$"), group=-199)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: _text(u,c,B)), group=-198)
    B._startup_button_firewall = True
