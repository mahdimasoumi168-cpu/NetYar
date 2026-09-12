"""Canonical Telegram UI: inline menus + one persistent restart button.

All normal menus use inline buttons. The only persistent reply-keyboard button
is «🔄 شروع مجدد», which executes the same flow as /start.
"""
from collections import OrderedDict
import threading
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, CommandHandler, ApplicationHandlerStop, filters

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


def reassert(B):
    """Re-apply canonical keyboard hooks after all legacy compatibility layers."""
    B.kb = _inline_kb
    B.ReplyKeyboardMarkup = _InlineOnlyReplyKeyboard
    B.restart_keyboard = restart_keyboard
    try:
        B.__dict__["ReplyKeyboardMarkup"] = _InlineOnlyReplyKeyboard
    except Exception:
        pass


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


def install(app, B):
    if getattr(B, "_netyar_no_reply_keyboard", False):
        reassert(B)
        return

    reassert(B)
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

    # Inline callbacks are owned exclusively by telegram_universal_button_guard.
    # The old dispatcher here caused the same click to be routed twice.
    B._netyar_no_reply_keyboard = True
    reassert(B)
