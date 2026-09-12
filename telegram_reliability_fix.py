"""Telegram production watchdog.

Keeps the single long-polling Telegram updater alive without creating a second
poller. The normal startup path remains responsible for initial setup; this
layer only recovers an updater that has unexpectedly stopped after startup.
"""
import asyncio
import logging

log = logging.getLogger("netyar.telegram.reliability")


async def _watch(server):
    while True:
        try:
            await asyncio.sleep(30)
            app = getattr(server, "telegram_app", None)
            if app is None:
                continue
            updater = getattr(app, "updater", None)
            if updater is None:
                continue
            if not getattr(server, "telegram_ready", False):
                continue
            if getattr(updater, "running", False):
                continue

            # Never create a second poller. PTB exposes the running state on
            # the updater; only restart when that state is definitely false.
            log.warning("Telegram updater stopped unexpectedly; restarting polling")
            try:
                await app.bot.delete_webhook(drop_pending_updates=False)
            except Exception:
                log.exception("Telegram webhook cleanup before recovery failed")
            try:
                await updater.start_polling(allowed_updates=None)
                server.telegram_ready = True
                log.warning("Telegram polling recovery completed")
            except Exception:
                server.telegram_ready = False
                log.exception("Telegram polling recovery failed")
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Telegram reliability watchdog failed")


def install():
    import server
    if getattr(server, "_telegram_reliability_fix_installed", False):
        return

    original_initialize = server._initialize_integrations

    async def initialize():
        await original_initialize()
        if getattr(server, "_telegram_reliability_watchdog", None) is None:
            server._telegram_reliability_watchdog = asyncio.create_task(_watch(server))
            log.info("Telegram reliability watchdog started")

    server._initialize_integrations = initialize
    server._telegram_reliability_fix_installed = True
