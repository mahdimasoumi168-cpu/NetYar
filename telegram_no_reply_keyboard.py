"""Canonical Telegram inline-only UI.

Legacy reply keyboards are removed. Inline buttons are routed through the same
text router used by normal messages, including after a restart/deploy.
"""
from collections import OrderedDict
import threading
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

log = logging.getLogger("netyar.telegram.inline_only")
_ACTIONS = OrderedDict()
_LOCK = threading.Lock()
_SEQ = 0
_REMOVED = set()


def _remember(label):
    global _SEQ
    with _LOCK:
        _SEQ += 1
        key = f"ik:{_SEQ}"
        _ACTIONS[key] = str(label)
        while len(_ACTIONS) > 3000:
            _ACTIONS.popitem(last=False)
    return key


def _inline_kb(rows):
    out = []
    for row in rows or []:
        buttons = []
        for item in row or []:
            label = str(item[1]) if isinstance(item, (tuple, list)) and len(item) >= 2 else str(item)
            if label:
                buttons.append(InlineKeyboardButton(label, callback_data=_remember(label)))
        if buttons:
            out.append(buttons)
    return InlineKeyboardMarkup(out)


class _InlineOnlyReplyKeyboard:
    def __new__(cls, keyboard, *args, **kwargs):
        return _inline_kb(keyboard)


async def _remove_legacy_keyboard(message):
    if not message:
        return
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None or chat_id in _REMOVED:
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
    await _remove_legacy_keyboard(getattr(update, "effective_message", None))


def _button_label_from_message(q):
    try:
        markup = getattr(q.message, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row:
                if getattr(button, "callback_data", None) == str(q.data or ""):
                    return str(getattr(button, "text", "") or "").strip()
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

    await q.answer()
    await _remove_legacy_keyboard(q.message)
    original = getattr(q.message, "text", None)

    try:
        # IMPORTANT: python-telegram-bot exposes callback messages through
        # effective_message, while legacy NetYar routers read update.message.
        # Bridge both fields so an inline click follows exactly the same path
        # as a normal text message instead of falling into the generic error.
        try:
            object.__setattr__(update, "message", q.message)
        except Exception:
            pass
        try:
            object.__setattr__(q.message, "text", label)
            await B.router(update, context)
        finally:
            try:
                object.__setattr__(q.message, "text", original)
            except Exception:
                pass
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

    app.add_handler(MessageHandler(filters.ALL, _remove_on_message), group=-200)
    app.add_handler(CallbackQueryHandler(lambda u, c: _inline_callback(u, c, B), pattern=r"^ik:"), group=-98)

    old_start = B.start

    async def start_without_reply_keyboard(update, context):
        await _remove_legacy_keyboard(getattr(update, "effective_message", None))
        return await old_start(update, context)

    B.start = start_without_reply_keyboard
    B._netyar_no_reply_keyboard = True
