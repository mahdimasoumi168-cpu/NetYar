"""Central Telegram keyboard policy for contextual cancel buttons.

Cancel is shown only while the user is inside a multi-step/input flow. It is
not shown on the normal user or partner home menus, where it is redundant and
can be mistaken for a global action.
"""
from telegram import InlineKeyboardMarkup


def _without_cancel(markup):
    """Remove only a trailing cancel row while preserving keyboard type."""
    if markup is None:
        return None
    rows = getattr(markup, "inline_keyboard", None)
    if rows is not None:
        rows = list(rows)
        if rows:
            last = list(rows[-1])
            labels = [str(getattr(b, "text", "")) for b in last]
            if any("لغو" in x or "Cancel" in x or "إلغاء" in x for x in labels):
                rows.pop()
        return InlineKeyboardMarkup(rows)
    rows = getattr(markup, "keyboard", None)
    if rows is not None:
        rows = list(rows)
        if rows:
            labels = [str(x) for x in rows[-1]]
            if any("لغو" in x or "Cancel" in x or "إلغاء" in x for x in labels):
                rows.pop()
        return B.kb(rows)
    return markup


def install(B):
    original_main = B.main
    original_partner_kb = B.partner_kb

    def main(uid):
        # UI policy v2 returns an InlineKeyboardMarkup. Older versions returned
        # a reply keyboard. Support both so this policy never breaks startup.
        return _without_cancel(original_main(uid))

    def partner_kb(lang="fa"):
        # Partner home menu: keep navigation/exit, but no global Cancel.
        return B.kb([
            ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی"],
            ["🚪 خروج از پنل"],
        ])

    B.main = main
    B.partner_kb = partner_kb
    return True
