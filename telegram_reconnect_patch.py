"""Telegram connectivity guard.

Production uses long polling on Railway. This patch must never recreate a
webhook after polling has started.
"""
import logging

log = logging.getLogger("netyar.telegram_reconnect")


def install():
    import server
    if getattr(server, "_netyar_telegram_reconnect_patch", False):
        return

    original = getattr(server, "_initialize_integrations", None)
    if original is None:
        return

    async def wrapped():
        await original()
        app = getattr(server, "telegram_app", None)
        if app is None:
            return

        # Polling is the only supported production mode here. Never call
        # set_webhook from the reconnect guard, even if an old Railway
        # variable still contains TELEGRAM_USE_WEBHOOK=true.
        server.telegram_ready = True
        log.info("Telegram reconnect guard: polling mode active")

    server._initialize_integrations = wrapped
    server._netyar_telegram_reconnect_patch = True
    log.info("Telegram reconnect guard installed")
