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

# Must be installed after server exists: the canonical server reapplies its
# generic Rubika patch on every update, so this guard restores the Iranian
# subscriber routing afterward.
import rubika_iranian_restore
rubika_iranian_restore.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
