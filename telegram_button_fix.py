"""Final Telegram reply-keyboard sanitizer.

Historical UI patches in this project can accidentally turn an emoji/button
label into Markdown/HTML link markup. ReplyKeyboard buttons must contain the
literal display text only. Sanitize at the final keyboard-construction point,
not just at one helper, so every path (including cancel/back flows) is covered.
"""
import re

_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)")
_HTML_LINK_RE = re.compile(r"<a\s+[^>]*>(.*?)</a>", flags=re.I | re.S)


def _clean_text(value):
    if not isinstance(value, str):
        return value
    value = _LINK_RE.sub(r"\1", value)
    value = _HTML_LINK_RE.sub(r"\1", value)
    return value.strip()


def _clean_button(item):
    # Normal project keyboards are strings. If a historical patch already
    # supplied a Telegram KeyboardButton object, rebuild it from its visible
    # text so stale markup cannot survive into the final ReplyKeyboardMarkup.
    try:
        from telegram import KeyboardButton
        if isinstance(item, KeyboardButton):
            return KeyboardButton(text=_clean_text(item.text))
    except Exception:
        pass
    return _clean_text(item)


def _clean_rows(rows):
    return [[_clean_button(item) for item in row] for row in (rows or [])]


def install():
    import bot as B
    if getattr(B, "_netyar_telegram_button_fix", False):
        return

    original_kb = B.kb
    original_markup = B.ReplyKeyboardMarkup

    def clean_kb(rows):
        return original_kb(_clean_rows(rows))

    class CleanReplyKeyboardMarkup(original_markup):
        def __init__(self, keyboard, *args, **kwargs):
            super().__init__(_clean_rows(keyboard), *args, **kwargs)

    # Keep both layers protected. This prevents a later/legacy path from
    # bypassing bot.kb and reintroducing malformed labels.
    B.kb = clean_kb
    B.ReplyKeyboardMarkup = CleanReplyKeyboardMarkup
    B._netyar_telegram_button_fix = True
