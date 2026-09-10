"""Final Telegram reply-keyboard sanitizer.

Important: this layer must pass plain strings to the legacy keyboard helper.
Passing KeyboardButton objects into that helper causes it to call str(item),
which leaks Python representations such as KeyboardButton(...) into the UI.
"""
import re

_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)")
_HTML_LINK_RE = re.compile(r"<a\s+[^>]*>(.*?)</a>", flags=re.I | re.S)


def _clean_text(value):
    if not isinstance(value, str):
        value = getattr(value, "text", str(value))
    value = _LINK_RE.sub(r"\1", value)
    value = _HTML_LINK_RE.sub(r"\1", value)
    return value.strip()


def _clean_button(item):
    # Always return a plain string. Never return KeyboardButton here because
    # the historical B.kb helper may stringify non-string values.
    return _clean_text(item)


def _clean_rows(rows):
    return [[_clean_button(item) for item in row] for row in (rows or [])]


def install():
    import bot as B
    from telegram import ReplyKeyboardMarkup

    if getattr(B, "_netyar_telegram_button_fix", False):
        return

    original_kb = B.kb
    original_markup = B.ReplyKeyboardMarkup

    def clean_kb(rows):
        return original_kb(_clean_rows(rows))

    class CleanReplyKeyboardMarkup(original_markup):
        def __init__(self, keyboard, *args, **kwargs):
            super().__init__(_clean_rows(keyboard), *args, **kwargs)

    B.kb = clean_kb
    B.ReplyKeyboardMarkup = CleanReplyKeyboardMarkup
    B._netyar_telegram_button_fix = True
