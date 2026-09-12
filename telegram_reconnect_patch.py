"""Telegram connectivity guard.

Production uses long polling on Railway. This patch never creates a webhook
and never marks Telegram ready unless the underlying initializer succeeded.
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
        if getattr(server, "telegram_ready", False):
            log.info("Telegram reconnect guard: polling mode active")
        else:
            log.error("Telegram reconnect guard: polling is NOT active")

    server._initialize_integrations = wrapped
    server._netyar_telegram_reconnect_patch = True
    log.info("Telegram reconnect guard installed")
