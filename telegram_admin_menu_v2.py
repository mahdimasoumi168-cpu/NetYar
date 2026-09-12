"""Small additive admin-menu layer; no routing monkey-patches beyond menu composition."""
from telegram import InlineKeyboardButton

def install(B):
    import telegram_admin_plus as A
    if getattr(A,"_ticket_menu_added",False):return
    old=A._admin_menu
    def menu():
        m=old();rows=[list(r) for r in m.inline_keyboard];rows.insert(-1,[InlineKeyboardButton("🎫 تیکت و پیام همکاران",callback_data="tk:partners")]);return type(m)(rows)
    A._admin_menu=menu;A._ticket_menu_added=True
