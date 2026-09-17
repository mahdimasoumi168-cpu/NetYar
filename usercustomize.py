"""Process-wide asyncio compatibility for legacy NetYar installers.

Python forbids asyncio.run() while another event loop is running in the same
thread. NetYar still has legacy synchronous installers that call asyncio.run
from FastAPI startup, so execute those legacy awaitables in a short-lived
worker thread instead of nesting event loops.
"""
import asyncio
import inspect
import threading

_REAL_RUN = asyncio.run


def _run_legacy(awaitable, *args, **kwargs):
    if not inspect.isawaitable(awaitable):
        return None
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _REAL_RUN(awaitable, *args, **kwargs)

    box = {"value": None, "error": None}

    def worker():
        try:
            box["value"] = _REAL_RUN(awaitable, *args, **kwargs)
        except BaseException as exc:
            box["error"] = exc

    t = threading.Thread(target=worker, name="netyar-legacy-asyncio", daemon=True)
    t.start()
    t.join()
    if box["error"] is not None:
        raise box["error"]
    return box["value"]


asyncio.run = _run_legacy
