"""Final Telegram menu deduplication guard.

Keeps one canonical partner-pricing entry in the admin menu. Older layers can
add their own pricing entry, so this final layer removes duplicate pricing
buttons while preserving their unrelated controls.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def install(app, B):
    if getattr(B, "_final_menu_dedup_guard", False):
        return
    import telegram_admin_plus as A
    old_menu = A._admin_menu

    def menu():
        markup = old_menu()
        rows = []
        pricing_seen = False
        for row in markup.inline_keyboard:
            kept = []
            for button in row:
                text = str(getattr(button, "text", "") or "")
                data = str(getattr(button, "callback_data", "") or "")
                is_pricing = (
                    "قیمت‌گذاری" in text or "قیمت گذاری" in text or
                    "قیمت اختصاصی همکار" in text or
                    data in {"adm:partner_prices_seq", "adm:partner_price_adjust_final"}
                )
                if is_pricing:
                    if pricing_seen:
                        continue
                    pricing_seen = True
                    kept.append(InlineKeyboardButton(
                        "📈 قیمت‌گذاری تک‌تک خدمات همکار",
                        callback_data="adm:partner_price_adjust_final",
                    ))
                else:
                    kept.append(button)
            if kept:
                rows.append(kept)
        if not pricing_seen:
            rows.append([InlineKeyboardButton(
                "📈 قیمت‌گذاری تک‌تک خدمات همکار",
                callback_data="adm:partner_price_adjust_final",
            )])
        return InlineKeyboardMarkup(rows)

    A._admin_menu = menu
    B._final_menu_dedup_guard = True
