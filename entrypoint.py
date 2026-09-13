"""Production entrypoint for Railway and local execution.

The FastAPI server owns application startup/shutdown. Telegram polling is
started exactly once by server.py after the canonical Application is built.
"""
import os
import logging

import uvicorn
import server
import bale_bootstrap

bale_bootstrap.install(server)


@server.api.on_event("startup")
async def _install_partner_logout_fix():
    try:
        import telegram_partner_logout_fix as fix
        import bot as B
        fix.install(B)
    except Exception:
        logging.getLogger("netyar.entrypoint").exception("partner logout fix unavailable")

    try:
        import telegram_language_consistency as language_lock
        import bot as B
        language_lock.install(B)
    except Exception:
        logging.getLogger("netyar.entrypoint").exception("final language lock unavailable")

    try:
        import telegram_cancel_policy as cancel_policy
        import bot as B
        cancel_policy.install(B)
    except Exception:
        logging.getLogger("netyar.entrypoint").exception("cancel policy unavailable")

    # Final Telegram overlay is intentionally installed LAST so no legacy
    # feature layer can overwrite these business rules afterwards.
    try:
        import final_stability_overlay as final_overlay
        import bot as B
        final_overlay.install(server.telegram_app, B)
        logging.getLogger("netyar.entrypoint").info("final Telegram stability overlay installed")
    except Exception:
        logging.getLogger("netyar.entrypoint").exception("final Telegram stability overlay unavailable")

    try:
        import final_government_payment_overlay as gov_overlay
        import bot as B
        gov_overlay.install(server.telegram_app, B)
        logging.getLogger("netyar.entrypoint").info("final government payment overlay installed")
    except Exception:
        logging.getLogger("netyar.entrypoint").exception("final government payment overlay unavailable")


def main():
    uvicorn.run(server.api,host="0.0.0.0",port=int(os.getenv("PORT","8000")),lifespan="on")


if __name__ == "__main__":
    main()
