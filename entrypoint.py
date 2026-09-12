"""Production entrypoint shared by Railway and local execution.

Keep Telegram on the clean canonical runtime and install only the Rubika
fallback needed when Rubika rejects the Railway webhook URL.
"""

import os
import sys

import telegram_runtime_clean

# server.py imports the runtime by the historical module name. Point that
# import at the clean canonical runtime before server is loaded.
sys.modules["telegram_runtime"] = telegram_runtime_clean

# Install only the isolated Rubika getUpdates fallback. Do NOT load the old
# runtime_patches chain: it contains legacy monkey-patches that can override
# Telegram partner-panel routing.
import rubika_polling_fallback
rubika_polling_fallback.install()

import uvicorn
import server


def main():
    """Start the FastAPI server with the application lifespan enabled."""
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
