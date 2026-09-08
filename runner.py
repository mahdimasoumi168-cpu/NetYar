"""Legacy entrypoint kept for Railway/backward compatibility.

The production architecture uses one FastAPI process (server.py) for both
Telegram and Rubika webhooks. Never start the old polling workers from here.
"""
import os
import sys

if __name__ == "__main__":
    os.execv(sys.executable, [sys.executable, "server.py"])
