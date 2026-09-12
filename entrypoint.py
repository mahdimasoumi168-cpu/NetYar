"""Production entrypoint shared by Railway and local execution."""
import os
import sys

import telegram_runtime_clean
sys.modules["telegram_runtime"] = telegram_runtime_clean

import uvicorn
import server

import production_stability
production_stability.install()

# Normalize Rubika sender/chat identities and make first contact reliable.
import rubika_stability_fix
rubika_stability_fix.install()

# Keep exactly one Rubika polling implementation.
import rubika_reliability_fix
rubika_reliability_fix.install()

# Never let the webhook path and polling path process the same Rubika update.
import rubika_webhook_guard
rubika_webhook_guard.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
