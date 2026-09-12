"""Production entrypoint shared by Railway and local execution.

Use the canonical FastAPI server directly and bind its Telegram runtime to
telegram_runtime_clean, which avoids the legacy monkey-patch chain.
"""

import os
import sys

import telegram_runtime_clean

# server.py imports the runtime by the historical module name.  Point that
# import at the clean canonical runtime before server is loaded.
sys.modules["telegram_runtime"] = telegram_runtime_clean

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
