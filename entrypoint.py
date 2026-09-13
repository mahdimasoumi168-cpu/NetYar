"""Production entrypoint for Railway and local execution."""
import os
import logging
import uvicorn
import server
import bale_bootstrap

bale_bootstrap.install(server)


@server.api.on_event("startup")
async def _install_final_telegram_patches():
    """Install operational layers in a deliberate order so every menu has a live owner."""
    log = logging.getLogger("netyar.entrypoint")
    modules = (
        "telegram_partner_logout_fix",
        "telegram_language_consistency",
        "telegram_cancel_policy",
        "final_stability_overlay",
        "final_government_payment_overlay",
        "telegram_price_dedup_guard",
        "telegram_final_layer_loader",
        "telegram_night_logout_final",
        "telegram_partner_login_fix",
        "telegram_offhours_partner_gate_v2",
        "telegram_admin_plus",
        "telegram_admin_power",
        "telegram_final_admin_menu_fix",
        "telegram_final_ops_overlay",
        "telegram_button_stability_final",
        "telegram_service_billing_v3_fix",
        "telegram_partner_ui_fix",
        "telegram_request_control_v2",
        "telegram_government_family_code_fix",
    )

    for module_name in modules:
        try:
            module = __import__(module_name)
            import bot as B
            if module_name in {
                "telegram_partner_logout_fix",
                "telegram_language_consistency",
                "telegram_cancel_policy",
            }:
                module.install(B)
            else:
                module.install(server.telegram_app, B)
            log.info("telegram layer installed: %s", module_name)
        except Exception:
            log.exception("telegram layer unavailable: %s", module_name)

    for module_name, label in (
        ("telegram_ui_policy_v2", "telegram canonical UI installed"),
        ("telegram_absolute_fix", "telegram absolute operational router installed last"),
        ("telegram_operational_continuation_guard", "telegram operational continuation guard installed last"),
        ("telegram_admin_request_reliability_fix", "telegram admin request reliability fix installed last"),
        ("telegram_partner_chat_reliability", "telegram partner chat reliability installed last"),
        ("telegram_final_notification_reliability", "telegram final notification reliability installed last"),
    ):
        try:
            module = __import__(module_name)
            import bot as B
            module.install(server.telegram_app, B)
            log.info(label)
        except Exception:
            log.exception("telegram layer unavailable: %s", module_name)


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
