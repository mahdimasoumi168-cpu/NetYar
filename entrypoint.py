"""Production entrypoint for Railway and local execution."""
import os
import logging
import uvicorn
import server
import bale_bootstrap

bale_bootstrap.install(server)


@server.api.on_event("startup")
async def _install_final_telegram_patches():
    # Final Telegram reliability stack. Keep the last stability layer at the
    # highest handler priority so legacy duplicate routers cannot consume the
    # same button/message first.
    for module_name in (
        "telegram_partner_logout_fix",
        "telegram_language_consistency",
        "telegram_cancel_policy",
        "final_stability_overlay",
        "final_government_payment_overlay",
        "telegram_price_dedup_guard",
        "telegram_final_layer_loader",
        "telegram_offhours_partner_gate_v2",
        "telegram_final_admin_menu_fix",
        "telegram_final_ops_overlay",
        "telegram_button_stability_final",
    ):
        try:
            module=__import__(module_name)
            import bot as B
            if module_name in {"telegram_partner_logout_fix","telegram_language_consistency","telegram_cancel_policy"}:
                module.install(B)
            else:
                module.install(server.telegram_app,B)
            logging.getLogger("netyar.entrypoint").info("%s installed",module_name)
        except Exception:
            logging.getLogger("netyar.entrypoint").exception("%s unavailable",module_name)


def main():
    uvicorn.run(server.api,host="0.0.0.0",port=int(os.getenv("PORT","8000")),lifespan="on")


if __name__ == "__main__":
    main()
