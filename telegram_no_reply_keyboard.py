"""Canonical Telegram UI: one persistent restart button, all other options inline.

Telegram reply keyboards are intentionally reduced to a single persistent
"🔄 شروع مجدد" button. Service/admin/partner options are rendered as inline
buttons attached to the message instead of a large keyboard below the chat.
"""
from collections import OrderedDict
import threading
import logging
from types import SimpleNamespace
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup as _NativeReplyKeyboardMarkup, ReplyKeyboardRemove
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


def _restart_kb():
    return _NativeReplyKeyboardMarkup([["🔄 شروع مجدد"]], resize_keyboard=True, one_time_keyboard=False)


class _RestartOnlyReplyKeyboard:
    """Compatibility shim: every legacy reply keyboard becomes restart-only."""
    def __new__(cls, keyboard=None, *args, **kwargs):
        return _restart_kb()


async def _remove_legacy_keyboard(message):
    if not message:
        return
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None or chat_id in _REMOVED:
        return
    # Do not remove the persistent restart keyboard. This function only clears
    # keyboards that may have been sent by an older deployment before this UI
    # policy was installed.
    return


async def _remove_on_message(update, context):
    # Kept as a high-priority compatibility hook; the restart-only keyboard is
    # deliberately persistent and must not be removed on every message.
    return


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


def _message_update_from_callback(update, q):
    return SimpleNamespace(
        update_id=getattr(update, "update_id", None),
        message=q.message,
        effective_message=q.message,
        effective_user=q.from_user,
        effective_chat=getattr(q.message, "chat", None),
        callback_query=q,
    )


async def _inline_callback(update, context, B):
    q = update.callback_query
    key = str(q.data or "")
    label = _ACTIONS.get(key) or _button_label_from_message(q)
    if not label:
        await q.answer("این گزینه دیگر معتبر نیست؛ لطفاً از منوی فعلی استفاده کنید.")
        return

    await q.answer()
    proxy = _message_update_from_callback(update, q)
    try:
        object.__setattr__(q.message, "text", label)
        await B.router(proxy, context)
    except Exception:
        log.exception("Inline button routing failed: %s", label)
        try:
            await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره همین گزینه را بزنید.", reply_markup=_restart_kb())
        except Exception:
            pass
    finally:
        try:
            object.__setattr__(q.message, "text", None)
        except Exception:
            pass


async def _restart(update, context, B):
    msg = getattr(update, "effective_message", None)
    text = str(getattr(msg, "text", "") or "").strip()
    if text not in {"🔄 شروع مجدد", "شروع مجدد", "/start", "start"}:
        return
    uid = update.effective_user.id
    B.S[uid] = {}
    await B.start(update, context)


def install(app, B):
    if getattr(B, "_netyar_restart_only_keyboard", False):
        return

    # B.kb is the canonical UI builder: all menus become inline buttons.
    B.kb = _inline_kb
    # Any legacy code importing/using ReplyKeyboardMarkup is forced to expose
    # only the single persistent restart button.
    B.ReplyKeyboardMarkup = _RestartOnlyReplyKeyboard

    for module_name in (
        "telegram_admin_plus",
        "telegram_ux_billing",
        "telegram_button_fix",
        "sitecustomize",
    ):
        try:
            module = __import__(module_name)
            if hasattr(module, "ReplyKeyboardMarkup"):
                module.ReplyKeyboardMarkup = _RestartOnlyReplyKeyboard
        except Exception:
            pass

    app.add_handler(MessageHandler(filters.ALL, _remove_on_message), group=-200)
    app.add_handler(CallbackQueryHandler(lambda u, c: _inline_callback(u, c, B), pattern=r"^ik:"), group=-98)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _restart(u, c, B), group=-97))

    old_start = B.start

    async def start_with_restart_keyboard(update, context):
        result = await old_start(update, context)
        try:
            await update.effective_message.reply_text("🔄", reply_markup=_restart_kb())
        except Exception:
            pass
        return result

    B.start = start_with_restart_keyboard
    B._netyar_restart_only_keyboard = True
