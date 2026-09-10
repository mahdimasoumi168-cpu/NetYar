"""Normalize Telegram reply-keyboard labels before sending them.

Some historical UI layers can accidentally turn emoji into Markdown image/link
syntax such as ``[👥](https://web.telegram.org/...)``. Telegram reply keyboard
buttons must contain plain display text, so strip only the Markdown wrapper and
keep the human-readable label.
"""
import re

_LINK_RE = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)")


def _clean_text(value):
    if not isinstance(value, str):
        return value
    value = _LINK_RE.sub(r"\1", value)
    # Also remove accidental HTML anchors while preserving visible text.
    value = re.sub(r"<a\s+[^>]*>(.*?)</a>", r"\1", value, flags=re.I | re.S)
    return value.strip()


def _clean_rows(rows):
    return [[_clean_text(item) for item in row] for row in rows]


def install():
    import bot as B
    if getattr(B, "_netyar_telegram_button_fix", False):
        return

    original_kb = B.kb

    def clean_kb(rows):
        return original_kb(_clean_rows(rows))

    B.kb = clean_kb
    B._netyar_telegram_button_fix = True
