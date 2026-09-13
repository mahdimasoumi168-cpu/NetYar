"""Production entrypoint for Railway and local execution."""
import os
import logging
import uvicorn
import server
import bale_bootstrap

bale_bootstrap.install(server)


@server.api.on_event("startup")
async def _install_final_telegram_patches():
    for module_name in (
        "telegram_partner_logout_fix",
        "telegram_language_consistency",
        "telegram_cancel_policy",
        "final_stability_overlay",
        "final_government_payment_overlay",
        "telegram_price_dedup_guard",
    ):
        try:
            module=__import__(module_name)
            import bot as B
            if module_name=="telegram_partner_logout_fix":
                module.install(B)
            elif module_name in {"telegram_language_consistency","telegram_cancel_policy"}:
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
