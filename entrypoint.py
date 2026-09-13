"""Production entrypoint for Railway and local execution.

The FastAPI server owns application startup/shutdown. Telegram polling is
started exactly once by server.py after the canonical Application is built.
"""
import os

import uvicorn
import server
import bale_bootstrap

# Install the Bale webhook adapter before FastAPI startup handlers are run.
bale_bootstrap.install(server)


@server.api.on_event("startup")
async def _install_partner_logout_fix():
    # Run after the server's integration startup so later Telegram feature
    # layers cannot replace the logout behavior. A permanent logout clears
    # authentication/pending states and never starts p_phone automatically.
    try:
        import telegram_partner_logout_fix as fix
        import bot as B
        fix.install(B)
    except Exception:
        import logging
        logging.getLogger("netyar.entrypoint").exception("partner logout fix unavailable")

    # Apply the contextual Cancel policy after all Telegram feature layers
    # have installed/replaced their keyboard helpers.
    try:
        import telegram_cancel_policy as cancel_policy
        import bot as B
        cancel_policy.install(B)
    except Exception:
        import logging
        logging.getLogger("netyar.entrypoint").exception("cancel policy unavailable")


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
