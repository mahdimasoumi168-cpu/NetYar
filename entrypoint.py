"""NetYar production entrypoint.

There is exactly one Telegram application builder: ``telegram_runtime_clean``
via ``server._initialize_integrations``.  This file must not install Telegram
handlers itself; doing so created two competing runtimes and made GitHub
changes appear to have no effect on the live bot.
"""
import logging
import os
import uvicorn
import bale_bootstrap
import production_stability
import rubika_bootstrap_final
import server

NETYAR_TELEGRAM_BUILD = "2026-09-17-single-runtime-v5"
log = logging.getLogger("netyar.entrypoint")

# Non-Telegram integrations are initialized here. Telegram is intentionally
# owned only by server -> telegram_runtime_clean.build().
bale_bootstrap.install(server)
rubika_bootstrap_final.install(server)
production_stability.install()


def main():
    port = int(os.getenv("PORT", "8000"))
    log.info("NetYar production entrypoint build=%s", NETYAR_TELEGRAM_BUILD)
    log.info("Telegram runtime owner=telegram_runtime_clean.build")
    uvicorn.run(server.api, host="0.0.0.0", port=port, lifespan="on")


if __name__ == "__main__":
    main()
