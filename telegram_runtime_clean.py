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
import partner_price_exact
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
import admin_control_v4
import telegram_global_stability
import final_terminal_navigation_guard
import telegram_start_flow_fix
import telegram_ultimate_hardening
import telegram_final_control
import telegram_sim_service
import telegram_sim_service_v2
import telegram_public_tracking
import telegram_tracking_router
import telegram_partner_registration
import telegram_absolute_fix


def build():
    final_requirements_patch.install()
    final_ux_hardening.install()
    final_navigation_language_stability.install()
    cross_platform_stability_final.install()
    admin_control_v4.install()
    app = B.build()
    telegram_ticket_reliability.install(app, B)
    telegram_panels.install(app, B)
    telegram_admin_partner_chat.install(app, B)
    telegram_service_notifications.install(app, B)
    partner_pricing.install_telegram(app, B)
    partner_price_exact.install_telegram(app, B)
    telegram_partner_price_adjustment.install(app, B)
    telegram_gov_documents_flow.install(app, B)
    telegram_ux_billing.install(app, B)
    telegram_start_flow_fix.install(B)
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
    telegram_admin_partner_chat.install(app, B)
    telegram_global_stability.install(B)
    final_terminal_navigation_guard.install(app, B)
    telegram_ultimate_hardening.install(app, B)
    telegram_final_control.install(app, B)
    telegram_sim_service.install(app, B)
    telegram_sim_service_v2.install(app, B)
    telegram_public_tracking.install(app, B)
    telegram_tracking_router.install(B)
    # Partner onboarding is installed after the generic partner login layer so
    # new accounts are routed through the new-registration workflow first.
    telegram_partner_registration.install(app, B)
    # Absolute last Telegram callback/navigation owner.
    telegram_absolute_fix.install(app, B)
    # Reassert inline keyboard after every legacy UI monkey-patch.
    telegram_no_reply_keyboard.reassert(B)
    return app
