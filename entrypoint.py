"""Production entrypoint shared by Railway and local execution."""
import os
import sys

import telegram_runtime_clean
sys.modules["telegram_runtime"] = telegram_runtime_clean

import rubika_polling_fallback
rubika_polling_fallback.install()

import uvicorn
import server

import production_stability
production_stability.install()

# Restore the Iranian subscriber route after the generic server Rubika patch.
import rubika_iranian_restore
rubika_iranian_restore.install()

# Replace the old blocking polling loop with a short-timeout, concurrent loop.
import rubika_reliability_fix
rubika_reliability_fix.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
