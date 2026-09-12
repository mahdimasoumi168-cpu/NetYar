"""Canonical Telegram UI: inline menus + one persistent restart button.

All normal menus use inline buttons. The only persistent reply-keyboard button
is «🔄 شروع مجدد», which executes the same flow as /start.
"""
from collections import OrderedDict
import threading
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.inline_only")
_ACTIONS = OrderedDict()
_LOCK = threading.Lock()
_SEQ = 0
_REMOVED = set()
_RESTART_CHATS = set()


def _remember(label):
    global _SEQ
    with _LOCK:
        _SEQ += 1
        key = f"ik:{_SEQ}"
        _ACTIONS[key] = str(label)
        while len(_ACTIONS) > 3000:
            _ACTIONS.popitem(last=False)
    return key


def _clean_label(label):
    s = str(label or "").strip()
    for prefix in ("🟦 ", "🟩 ", "🟨 ", "🔵 "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s


def _inline_kb(rows):
    out = []
    for row in rows or []:
        buttons = []
        for item in row or []:
            label = str(item[1]) if isinstance(item, (tuple, list)) and len(item) >= 2 else str(item)
            label = _clean_label(label)
            if label:
                buttons.append(InlineKeyboardButton(label, callback_data=_remember(label)))
        if buttons:
            out.append(buttons)
    return InlineKeyboardMarkup(out)


class _InlineOnlyReplyKeyboard:
    """Compatibility shim: legacy B.ReplyKeyboardMarkup becomes inline."""
    def __new__(cls, keyboard, *args, **kwargs):
        return _inline_kb(keyboard)


def restart_keyboard():
    """The one and only persistent Telegram reply keyboard."""
    return ReplyKeyboardMarkup([["🔄 شروع مجدد"]], resize_keyboard=True, is_persistent=True)


async def _remove_legacy_keyboard(message):
    if not message:
        return
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None or chat_id in _REMOVED or chat_id in _RESTART_CHATS:
        return
    try:
        probe = await message.reply_text("\u2063", reply_markup=ReplyKeyboardRemove())
        _REMOVED.add(chat_id)
        try:
            await probe.delete()
        except Exception:
            pass
    except Exception:
        pass


async def _remove_on_message(update, context):
    msg = getattr(update, "effective_message", None)
    if getattr(msg, "text", None) == "🔄 شروع مجدد":
        return
    await _remove_legacy_keyboard(msg)


class _CallbackMessageProxy:
    """Message proxy that keeps Telegram's real reply methods but overrides text.

    Several legacy routers only inspect update.message.text. Passing a plain
    SimpleNamespace there loses Telegram Message methods; mutating q.message is
    also unsafe. This proxy gives the router the selected button text while all
    reply/edit/file operations continue to target the real Telegram message.
    """
    def __init__(self, message, text):
        self._message = message
        self.text = text

    def __getattr__(self, name):
        return getattr(self._message, name)


class _CallbackUpdateProxy:
    def __init__(self, update, q, label):
        message = _CallbackMessageProxy(q.message, label)
        self.update_id = getattr(update, "update_id", None)
        self.message = message
        self.effective_message = message
        self.effective_user = q.from_user
        self.effective_chat = getattr(q.message, "chat", None)
        self.callback_query = q


def _button_label_from_message(q):
    try:
        markup = getattr(q.message, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row:
                if getattr(button, "callback_data", None) == str(q.data or ""):
                    return _clean_label(getattr(button, "text", "") or "")
    except Exception:
        log.exception("inline button label recovery failed")
    return ""


async def _inline_callback(update, context, B):
    q = update.callback_query
    key = str(q.data or "")
    label = _ACTIONS.get(key) or _button_label_from_message(q)
    if not label:
        await q.answer("این گزینه دیگر معتبر نیست؛ لطفاً از منوی فعلی استفاده کنید.")
        return

    label = _clean_label(label)
    await q.answer()
    proxy = _CallbackUpdateProxy(update, q, label)
    try:
        # Route through the FINAL B.router so every existing service, partner,
        # admin and cancellation flow keeps its current behavior.
        await B.router(proxy, context)
    except Exception:
        log.exception("Inline button routing failed: %s", label)
        try:
            await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره همین گزینه را بزنید.")
        except Exception:
            pass


def install(app, B):
    if getattr(B, "_netyar_no_reply_keyboard", False):
        return

    B.kb = _inline_kb
    B.ReplyKeyboardMarkup = _InlineOnlyReplyKeyboard
    B.restart_keyboard = restart_keyboard

    for module_name in (
        "telegram_admin_plus",
        "telegram_ux_billing",
        "telegram_button_fix",
        "sitecustomize",
    ):
        try:
            module = __import__(module_name)
            if hasattr(module, "ReplyKeyboardMarkup"):
                module.ReplyKeyboardMarkup = _InlineOnlyReplyKeyboard
        except Exception:
            pass

    old_start = B.start

    async def _restart(update, context):
        result = await old_start(update, context)
        try:
            chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
            if chat_id is not None:
                _RESTART_CHATS.add(chat_id)
            await update.effective_message.reply_text("\u2063", reply_markup=restart_keyboard())
        except Exception:
            log.exception("failed to install restart keyboard")
        raise ApplicationHandlerStop

    app.add_handler(CommandHandler("start", _restart), group=-301)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^🔄 شروع مجدد$"), _restart), group=-300)
    app.add_handler(MessageHandler(filters.ALL, _remove_on_message), group=-200)
    # Must run before every legacy CallbackQueryHandler. Otherwise an older
    # callback handler can consume the update before the canonical label router.
    app.add_handler(CallbackQueryHandler(lambda u, c: _inline_callback(u, c, B), pattern=r"^ik:"), group=-10000)

    B._netyar_no_reply_keyboard = True
