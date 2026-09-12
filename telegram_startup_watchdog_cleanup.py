"""Disable the legacy Telegram watchdog task created by server.startup.

The canonical Telegram lifecycle is owned by telegram_single_poller_guard.
server.startup historically creates _integration_watchdog directly, so merely
replacing server._integration_watchdog does not stop that already-referenced
function. This wrapper cancels only the legacy watchdog task after startup;
it does not touch the Telegram Application or its single poller.
"""
from __future__ import annotations

import asyncio


def install() -> None:
    import server

    if getattr(server, "_netyar_startup_watchdog_cleanup_installed", False):
        return

    startup_list = getattr(server.api.router, "on_startup", [])
    for index, original in enumerate(list(startup_list)):
        if getattr(original, "__name__", "") != "startup":
            continue

        async def cleaned_startup(_original=original):
            await _original()
            current = asyncio.current_task()
            for task in asyncio.all_tasks():
                if task is current or task.done():
                    continue
                try:
                    coro = task.get_coro()
                    qualname = getattr(coro, "__qualname__", "")
                    name = getattr(coro, "__name__", "")
                    if "_integration_watchdog" in qualname or name == "_integration_watchdog":
                        task.cancel()
                except Exception:
                    continue

        startup_list[index] = cleaned_startup
        break

    server._netyar_startup_watchdog_cleanup_installed = True
