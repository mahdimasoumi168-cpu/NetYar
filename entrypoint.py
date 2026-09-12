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

# Keep a single Rubika polling implementation. The reliability layer also
# reuses the fallback module's dedupe/notification helpers without installing
# a second initialize wrapper or a second polling task.
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
