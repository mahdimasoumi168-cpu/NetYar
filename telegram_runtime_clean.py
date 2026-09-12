"""Canonical Telegram runtime."""

import bot as B
import telegram_panels
import telegram_admin_partner_chat
import telegram_service_notifications
import telegram_ux_billing
import telegram_gov_documents_flow
import telegram_admin_plus
import telegram_admin_entry
import telegram_admin_button_guard
import telegram_residence_booklet
import telegram_residence_booklet_guard
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
import telegram_request_resend_fa
import telegram_ticket_reliability
import final_requirements_patch
import final_ux_hardening
import final_navigation_language_stability
import cross_platform_stability_final
import final_terminal_navigation_guard


def build():
    """Build Telegram and install the focused production extensions."""
    final_requirements_patch.install()
    final_ux_hardening.install()
    final_navigation_language_stability.install()
    cross_platform_stability_final.install()

    app = B.build()
    telegram_ticket_reliability.install(app, B)
    telegram_panels.install(app, B)
    telegram_admin_partner_chat.install(app, B)
    telegram_service_notifications.install(app, B)
    partner_pricing.install_telegram(app, B)
    telegram_partner_price_adjustment.install(app, B)
    telegram_gov_documents_flow.install(app, B)
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
    telegram_partner_code_reliable.install(app, B)
    telegram_request_details_fix.install(app, B)
    telegram_request_resend_fa.install(app, B)

    telegram_residence_booklet_guard.install(app, B)

    # Re-apply admin/partner communication after legacy menu patches.
    telegram_admin_partner_chat.install(app, B)

    # Absolute final terminal layer: admin panel, Iranian -> partner panel,
    # partner ticket and ticket text must be consumed before legacy routers.
    final_terminal_navigation_guard.install(app, B)
    return app
