"""Telegram single-poller guard.

The production server is intentionally long-polling only. Older runtime layers
installed a second webhook cleanup watchdog, which was unnecessary and made the
Telegram lifecycle harder to reason about. This guard keeps exactly one
recovery loop and backs off on Telegram Conflict instead of repeatedly
restarting a competing poller.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("netyar.telegram.single_poller")


async def _safe_watch(server):
    """Recover a genuinely stopped updater without creating a second poller."""
    conflict_backoff = 60
    while True:
        try:
            await asyncio.sleep(30)
            app = getattr(server, "telegram_app", None)
            updater = getattr(app, "updater", None) if app else None
            if app is None or updater is None:
                continue
            if not getattr(server, "telegram_ready", False):
                continue
            if getattr(updater, "running", False):
                continue

            # The updater has stopped. Do not call start_polling while another
            # recovery attempt is already in progress.
            if getattr(server, "_telegram_single_recovery_lock", None) is None:
                server._telegram_single_recovery_lock = asyncio.Lock()
            lock = server._telegram_single_recovery_lock
            if lock.locked():
                continue

            async with lock:
                if getattr(updater, "running", False):
                    continue
                log.warning("Telegram updater stopped; attempting one controlled recovery")
                try:
                    await app.bot.delete_webhook(drop_pending_updates=False)
                    await updater.start_polling(allowed_updates=None)
                    server.telegram_ready = bool(getattr(updater, "running", False))
                    if server.telegram_ready:
                        conflict_backoff = 60
                        log.warning("Telegram polling recovery completed")
                    else:
                        log.error("Telegram polling recovery returned without a running updater")
                except Exception as exc:
                    # Telegram raises Conflict when another process/replica is
                    # polling the same bot token. Back off instead of hammering
                    # getUpdates and making the connection flap continuously.
                    server.telegram_ready = False
                    log.exception("Telegram polling recovery failed: %s", exc)
                    await asyncio.sleep(conflict_backoff)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Telegram single-poller watchdog failed")


async def _disabled_legacy_watchdog():
    """Compatibility replacement for the old webhook-deleting watchdog."""
    while True:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            return


def install() -> None:
    import server

    if getattr(server, "_telegram_single_poller_guard_installed", False):
        return

    # startup() schedules server._integration_watchdog(). Replace that legacy
    # watchdog before FastAPI startup so it cannot repeatedly mutate Telegram's
    # webhook state while long polling is active.
    server._integration_watchdog = _disabled_legacy_watchdog

    if getattr(server, "_telegram_single_poller_watchdog", None) is None:
        # _initialize_integrations is already wrapped by telegram_reliability_fix;
        # wrap it once more only to start our controlled recovery loop.
        original_initialize = server._initialize_integrations

        async def initialize():
            await original_initialize()
            task = getattr(server, "_telegram_single_poller_watchdog", None)
            if task is None or task.done():
                server._telegram_single_poller_watchdog = asyncio.create_task(_safe_watch(server))
                log.info("Telegram single-poller watchdog started")

        server._initialize_integrations = initialize

    server._telegram_single_poller_guard_installed = True
    log.info("Telegram single-poller guard installed")
