"""Telegram single-poller guard.

There is exactly one Telegram polling owner. Startup is retried when the
first polling attempt fails, and the watchdog only recovers a genuinely
stopped updater. No second poller is ever created while one is running.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("netyar.telegram.single_poller")


async def _start_polling_once(server, app):
    updater = getattr(app, "updater", None)
    if updater is None:
        raise RuntimeError("python-telegram-bot updater is unavailable")
    if getattr(updater, "running", False):
        server.telegram_ready = True
        return True

    await app.bot.delete_webhook(drop_pending_updates=False)
    await updater.start_polling(
        allowed_updates=None,
        drop_pending_updates=False,
        error_callback=getattr(server, "_telegram_polling_error_callback", None),
    )
    server.telegram_ready = bool(getattr(updater, "running", False))
    return server.telegram_ready


async def _safe_watch(server):
    """Recover a genuinely stopped updater without creating a second poller."""
    while True:
        try:
            await asyncio.sleep(30)
            app = getattr(server, "telegram_app", None)
            updater = getattr(app, "updater", None) if app else None
            if app is None or updater is None:
                continue
            if getattr(updater, "running", False):
                server.telegram_ready = True
                continue

            lock = getattr(server, "_telegram_single_recovery_lock", None)
            if lock is None:
                lock = server._telegram_single_recovery_lock = asyncio.Lock()
            if lock.locked():
                continue

            async with lock:
                if getattr(updater, "running", False):
                    server.telegram_ready = True
                    continue
                log.warning("Telegram updater stopped; controlled recovery starting")
                try:
                    ok = await _start_polling_once(server, app)
                    if ok:
                        log.warning("Telegram polling recovery completed")
                    else:
                        log.error("Telegram polling recovery returned without running updater")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    server.telegram_ready = False
                    # 409 Conflict means another poller may own this token.
                    # Back off instead of hammering getUpdates.
                    log.exception("Telegram polling recovery failed: %s", exc)
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Telegram single-poller watchdog failed")


def _disabled_legacy_watchdog(server=None):
    """Compatibility marker; server startup schedules its own watchdog."""
    async def idle():
        while True:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                return
    return idle()


def install() -> None:
    import server

    if getattr(server, "_telegram_single_poller_guard_installed", False):
        return

    # Disable the old server watchdog before FastAPI startup.
    server._integration_watchdog = _disabled_legacy_watchdog

    original_initialize = server._initialize_integrations

    async def initialize():
        # Run the normal initialization first. If Telegram startup failed,
        # retry the SAME application instead of constructing a second app.
        await original_initialize()
        app = getattr(server, "telegram_app", None)
        if app is None:
            log.error("Telegram application was not created")
            return

        if not getattr(server, "telegram_ready", False):
            lock = getattr(server, "_telegram_single_recovery_lock", None)
            if lock is None:
                lock = server._telegram_single_recovery_lock = asyncio.Lock()
            if not lock.locked():
                async with lock:
                    for attempt in range(1, 4):
                        try:
                            log.warning("Telegram startup recovery attempt %s/3", attempt)
                            if await _start_polling_once(server, app):
                                log.info("Telegram startup recovery succeeded")
                                break
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            log.exception("Telegram startup recovery attempt %s failed", attempt)
                            server.telegram_ready = False
                            if attempt < 3:
                                await asyncio.sleep(10 * attempt)

        task = getattr(server, "_telegram_single_poller_watchdog", None)
        if task is None or task.done():
            server._telegram_single_poller_watchdog = asyncio.create_task(_safe_watch(server))
            log.info("Telegram single-poller watchdog started")

    server._initialize_integrations = initialize
    server._telegram_single_poller_guard_installed = True
    log.info("Telegram single-poller guard installed")
