"""Canonical Telegram runtime.

Keep Telegram handler registration in one place. Feature modules are installed
here, but the polling lifecycle belongs exclusively to server/telegram guards.
"""
import bot as B

# Feature modules. Each module must only add/patch handlers and UI behaviour;
# none of them owns the Telegram polling lifecycle.
import telegram_panels,telegram_admin_partner_chat,telegram_service_notifications,telegram_ux_billing,telegram_gov_documents_flow,telegram_admin_plus,telegram_admin_entry,telegram_admin_button_guard
import telegram_residence_booklet,telegram_residence_booklet_guard,telegram_no_reply_keyboard,telegram_iranian_complaints,admin_editable_texts,partner_pricing,partner_price_exact,telegram_partner_price_adjustment,telegram_iranian_admin,telegram_partner_login_fix
import partner_balance_guard,partner_balance_reset,telegram_notification_guard,telegram_partner_code_reliable,telegram_request_details_fix,telegram_request_resend_fa,telegram_ticket_reliability
import final_requirements_patch,final_ux_hardening,final_navigation_language_stability,cross_platform_stability_final,admin_control_v4,telegram_global_stability,final_terminal_navigation_guard,telegram_start_flow_fix
import telegram_ultimate_hardening,telegram_final_control,telegram_sim_service,telegram_sim_service_v2,telegram_sim_partner_balance,telegram_public_tracking,telegram_tracking_router,telegram_partner_registration,telegram_absolute_fix,telegram_night_shift_access


def build():
    """Build the Telegram Application exactly once.

    No module in this function starts polling, creates a second Application, or
    installs another lifecycle/watchdog owner.
    """
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
    telegram_global_stability.install(B)
    final_terminal_navigation_guard.install(app, B)
    telegram_ultimate_hardening.install(app, B)
    telegram_final_control.install(app, B)
    telegram_sim_service.install(app, B)
    telegram_sim_service_v2.install(app, B)
    telegram_sim_partner_balance.install(app, B)
    telegram_public_tracking.install(app, B)
    telegram_tracking_router.install(B)
    telegram_partner_registration.install(app, B)
    telegram_absolute_fix.install(app, B)
    telegram_night_shift_access.install(app, B)

    # Reassert only the keyboard layer; this does not touch polling.
    telegram_no_reply_keyboard.reassert(B)
    return app
