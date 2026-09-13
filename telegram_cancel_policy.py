"""Central Telegram keyboard policy for contextual cancel buttons.

Keeps the canonical inline callback keyboards intact. Contextual cancel is
handled by the canonical UI router; this layer must never downgrade an inline
partner menu to a ReplyKeyboardMarkup.
"""

from telegram import InlineKeyboardMarkup


def _without_cancel(markup):
    if markup is None:
        return None
    rows = getattr(markup, "inline_keyboard", None)
    if rows is not None:
        rows = list(rows)
        if rows:
            last = list(rows[-1])
            labels = [str(getattr(b, "text", "")) for b in last]
            if any(x in {"❌ انصراف", "❌ Cancel", "❌ إلغاء"} for x in labels):
                rows.pop()
        return InlineKeyboardMarkup(rows)
    return markup


def install(B):
    original_main = B.main
    original_partner_kb = B.partner_kb
    original_cancel_kb = getattr(B, "cancel_kb", None)

    def main(uid):
        return _without_cancel(original_main(uid))

    def partner_kb(lang="fa"):
        # Preserve the canonical inline keyboard so every partner option keeps
        # its ui2 callback token and is handled by telegram_ui_policy_v2.
        return original_partner_kb(lang)

    B.main = main
    B.partner_kb = partner_kb
    if original_cancel_kb is not None:
        B.cancel_kb = original_cancel_kb
    return True
