"""Production entrypoint shared by Railway and local execution.

Use the canonical FastAPI server directly. The previous entrypoint loaded a
large legacy monkey-patch chain before startup; that chain could overwrite
Telegram handlers and button routing multiple times.
"""

import os

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
