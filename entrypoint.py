"""Production entrypoint shared by Railway and local execution."""

import os
import sys

import telegram_runtime_clean

# server.py imports the runtime by the historical module name. Point that
# import at the clean canonical runtime before server is loaded.
sys.modules["telegram_runtime"] = telegram_runtime_clean

# Install only the isolated Rubika fallback. Do not load the old runtime patch
# chain: it contains legacy monkey-patches that can override Telegram routing.
import rubika_polling_fallback
rubika_polling_fallback.install()

import uvicorn
import server

# Install small, idempotent production guards after server is loaded so they
# wrap the canonical routing functions used by both platforms.
import production_stability
production_stability.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
