"""Central Telegram keyboard policy for contextual cancel buttons.

Cancel is shown only while the user is inside a multi-step/input flow. It is
not shown on the normal user or partner home menus, where it is redundant and
can be mistaken for a global action.
"""

def install(B):
    original_main = B.main
    original_partner_kb = B.partner_kb

    def main(uid):
        # Rebuild the normal home menu without the global Cancel row.
        return B.kb([*original_main(uid).keyboard])

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
