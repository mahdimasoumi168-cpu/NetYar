"""Production entrypoint for Railway and local execution."""
import os
import logging
import uvicorn
import server
import bale_bootstrap

bale_bootstrap.install(server)


@server.api.on_event("startup")
async def _install_final_telegram_patches():
    """Install compatibility layers, then restore one canonical Telegram UI."""
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
        "telegram_final_admin_menu_fix",
        "telegram_final_ops_overlay",
        "telegram_button_stability_final",
        "telegram_service_billing_v3_fix",
        "telegram_partner_ui_fix",
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

    # Canonical UI first, then the final operational router owns partner
    # buttons and their follow-up messages without legacy collisions.
    try:
        import telegram_ui_policy_v2 as UI
        import bot as B
        UI.install(server.telegram_app, B)
        log.info("telegram canonical UI installed")
    except Exception:
        log.exception("telegram canonical UI unavailable")

    try:
        import telegram_absolute_fix as AF
        import bot as B
        AF.install(server.telegram_app, B)
        log.info("telegram absolute operational router installed last")
    except Exception:
        log.exception("telegram absolute operational router unavailable")


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
