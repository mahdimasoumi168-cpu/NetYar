"""Production entrypoint shared by Railway and local execution.

Telegram is the primary runtime.  Keep the process startup path free of
Rubika monkey-patches so a Rubika failure can never prevent Telegram from
starting.
"""
import os
import sys

# Use the single canonical Telegram runtime.  It builds one Application;
# server.py owns the only polling lifecycle.
import telegram_runtime_clean
sys.modules["telegram_runtime"] = telegram_runtime_clean

import uvicorn
import server

# Telegram-only stability guards.  These serialize updates/callbacks but do
# not create or start another polling loop.
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
