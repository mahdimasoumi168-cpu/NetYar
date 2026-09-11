"""Production entrypoint shared by Railway and local execution."""

import os

import uvicorn

from runtime_patches import install

server = install()


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
