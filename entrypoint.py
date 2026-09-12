"""Production entrypoint for Railway and local execution.

The FastAPI server owns application startup/shutdown. Telegram polling is
started exactly once by server.py after the canonical Application is built.
"""
import os

import uvicorn
import server


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
