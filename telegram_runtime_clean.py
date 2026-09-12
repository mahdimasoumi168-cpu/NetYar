"""Canonical Telegram runtime."""

import bot as B
import telegram_panels
import telegram_service_notifications
import telegram_ux_billing
import telegram_admin_plus
import telegram_admin_entry
import telegram_residence_booklet
import telegram_no_reply_keyboard
import telegram_iranian_complaints
import admin_editable_texts
import partner_pricing
import telegram_partner_price_adjustment
import telegram_iranian_admin
import telegram_partner_login_fix
import partner_balance_guard
import partner_balance_reset
import telegram_notification_guard
import telegram_partner_code_reliable
import telegram_request_details_fix


def build():
    """Build Telegram and install the focused production extensions."""
    app = B.build()
    telegram_panels.install(app, B)
    telegram_service_notifications.install(app, B)
    partner_pricing.install_telegram(app, B)
    telegram_partner_price_adjustment.install(app, B)
    telegram_ux_billing.install(app, B)
    telegram_admin_plus.install(app, B)
    telegram_admin_entry.install(app, B)
    telegram_residence_booklet.install(app, B)
    telegram_no_reply_keyboard.install(app, B)
    telegram_iranian_complaints.install(app, B)
    admin_editable_texts.install(app, B)
    telegram_iranian_admin.install(app, B)
    telegram_partner_login_fix.install(app, B)
    partner_balance_guard.install(B)
    partner_balance_reset.install(app, B)
    telegram_notification_guard.install(app, B)
    partner_balance_reset.install(app, B)
    telegram_partner_code_reliable.install(app, B)
    telegram_request_details_fix.install(app, B)
    return app
