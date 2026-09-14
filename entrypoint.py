"""NetYar production entrypoint.

Single HTTP runtime for Railway. PORT is supplied by Railway (currently 8080).
Telegram is initialized by the server integration bootstrap in webhook mode;
no polling is started here.
"""
import os
import uvicorn
import bale_bootstrap
import production_stability
import rubika_bootstrap_final
import server

NETYAR_TELEGRAM_BUILD = "2026-09-14-single-http-runtime"

# Keep non-Telegram integrations isolated. A failure in one platform must not
# prevent the HTTP service or Telegram from starting.
try:
    bale_bootstrap.install(server)
except Exception:
    pass
try:
    rubika_bootstrap_final.install(server)
except Exception:
    pass
try:
    production_stability.install()
except Exception:
    pass


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
