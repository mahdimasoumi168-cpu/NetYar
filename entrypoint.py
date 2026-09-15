"""NetYar production entrypoint.

The runtime layers are intentionally ordered: core guards first, service
flows in the middle, and final request/partner delivery layers last.  Existing
features are preserved; the final layers only harden routing and delivery.
"""
import inspect
import logging
import os

import uvicorn

import bale_bootstrap
import production_stability
import rubika_bootstrap_final
import server

NETYAR_TELEGRAM_BUILD = "2026-09-15-clean-runtime-v19"

bale_bootstrap.install(server)
rubika_bootstrap_final.install(server)
production_stability.install()

# Early/global Telegram guards. These must run before the normal service UI.
PRE_TELEGRAM_MODULES = (
    "telegram_global_cancel_v4",
    "request_language_actions",
    "telegram_partner_logout_fix",
    "telegram_language_consistency",
    "telegram_cancel_policy",
)

# Existing service/UI layers. Order is preserved from the working runtime;
# final compatibility layers are kept at the end so they can safely normalize
# behavior without replacing the original menus or options.
TELEGRAM_MODULES = (
    "telegram_absolute_offhours_guard",
    "telegram_government_phone_final",
    "telegram_phone_registry_and_stability",
    "telegram_final_hotfix_20260914",
    "telegram_fast_response_layer",
    "telegram_critical_input_logout_fix",
    "telegram_idle_session_reset",
    "telegram_input_continuation_guard",
    "telegram_admin_button_guard",
    "telegram_partner_pricing_stable",
    "telegram_partner_session_persistence",
    "telegram_management_destination_guard",
    "telegram_global_admin_guard",
    "telegram_universal_partner_guard",
    "final_stability_overlay",
    "final_government_payment_overlay",
    "telegram_price_dedup_guard",
    "telegram_government_flow_runtime_fix",
    "telegram_night_logout_final",
    "telegram_partner_login_fix",
    "telegram_offhours_partner_gate_v2",
    "telegram_admin_plus",
    "telegram_partner_code_reliable",
    "telegram_request_full_details_patch",
    "telegram_request_details_fix",
    "telegram_final_ops_overlay",
    "telegram_button_stability_final",
    "telegram_service_billing_v3_fix",
    "telegram_partner_ui_fix",
    "telegram_ux_billing",
    "telegram_request_control_v2",
    "telegram_government_family_code_fix",
    "telegram_ui_policy_v2",
    "telegram_absolute_fix",
    "telegram_operational_continuation_guard",
    "telegram_admin_request_reliability_fix",
    "telegram_partner_chat_reliability",
    "telegram_final_notification_reliability",
    "telegram_final_admin_partner_fix",
    "telegram_final_menu_dedup_guard",
    "telegram_final_user_state_guard",
    "telegram_service_dispatch_final",
    "telegram_information_input_final",
    "telegram_input_hardening_v3",
    "full_admin_control_patch",
    "production_final_patch",
    "telegram_announcement_media",
    "government_balance_postal_fix",
    "telegram_admin_menu_restore",
    "telegram_request_workflow_final",
    "telegram_universal_button_guard",
    "telegram_final_repair",
    "telegram_irancell_partner_service",
    "telegram_government_cancel_fix",
    "telegram_government_documents_v3",
    "telegram_government_validation_final",
    "telegram_management_stability_final",
    "telegram_final_ui_rebind",
    "telegram_final_partner_panel",
    "telegram_final_integration_guard",
    "telegram_partner_menu_final_v2",
    "telegram_partner_actions_final_guard",
    "telegram_partner_ticket_fix",
    "telegram_ticket_reliability",
    "telegram_ticket_media",
    # Final document flow is an override layer; it keeps the original UI but
    # guarantees the requested passport/booklet/card collection behavior.
    "telegram_government_final_override_v18",
    # Final request delivery is last so every stored attachment and admin
    # action is visible without removing the older management options.
    "telegram_final_request_delivery_v17",
)


def _install_module(name, app, bot, logger, *, pre=False):
    try:
        module = __import__(name)
        fn = getattr(module, "install", None)
        if not callable(fn):
            raise AttributeError("install() not found")

        sig = inspect.signature(fn)
        positional = [
            p
            for p in sig.parameters.values()
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        required = [p for p in positional if p.default is inspect.Parameter.empty]

        if len(required) >= 2 or len(positional) >= 2:
            fn(app, bot)
        elif len(required) == 1 or len(positional) == 1:
            fn(bot)
        else:
            fn()

        logger.info(
            "Telegram %s layer installed: %s",
            "pre-build" if pre else "runtime",
            name,
        )
    except Exception:
        logger.exception(
            "Telegram %s layer unavailable: %s",
            "pre-build" if pre else "runtime",
            name,
        )


def _install_telegram_layers(app, bot, logger):
    for name in PRE_TELEGRAM_MODULES:
        _install_module(name, app, bot, logger, pre=True)

    for name in TELEGRAM_MODULES:
        _install_module(name, app, bot, logger)

    # Legacy hardening modules that are intentionally loaded after the main
    # stack because some projects define their callbacks in the legacy layer.
    for name in (
        "telegram_government_strict_validation",
        "telegram_government_flow_hardening_v4",
        "telegram_government_v3_balance_guard",
        "telegram_government_final_flow_v7",
        "telegram_request_code_image_flow_v4",
        "telegram_final_bugfixes_v1",
    ):
        _install_module(name, app, bot, logger)

    # Patch the canonical admin notifier once. Do not install the same module
    # again through another explicit call; its internal guard owns idempotency.
    try:
        from telegram_request_full_details_patch import finalize

        finalize(bot)
        logger.info("Telegram complete-request notification finalizer installed")
    except Exception:
        logger.exception(
            "Telegram complete-request notification finalizer unavailable"
        )

    # desktop_agent_api_clean is deliberately last because it only exposes the
    # persisted request state and should not take over Telegram routing.
    _install_module("desktop_agent_api_clean", app, bot, logger)


def main():
    logger = logging.getLogger("netyar.entrypoint")
    logger.info("NetYar Telegram build=%s", NETYAR_TELEGRAM_BUILD)
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
