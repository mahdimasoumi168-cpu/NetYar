"""Telegram connectivity guard.

Polling is the production default on Railway. This patch must not re-create a
webhook after polling has started, otherwise Telegram delivery is interrupted.
"""
import asyncio
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

        use_webhook = server.os.getenv("TELEGRAM_USE_WEBHOOK", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if not use_webhook:
            # Long polling is already running; never call set_webhook here.
            server.telegram_ready = True
            log.info("Telegram reconnect guard: polling mode active")
            return

        expected = server.public_url("/telegram/update")
        last_error = None
        for attempt in range(6):
            try:
                info = await app.bot.get_webhook_info()
                actual = (info.url or "").rstrip("/")
                provider_error = (info.last_error_message or "").strip()
                if actual == expected.rstrip("/") and not provider_error:
                    server.telegram_ready = True
                    log.info("Telegram webhook healthy after reconnect check: attempt=%s", attempt + 1)
                    return
                if provider_error:
                    log.warning("Telegram webhook reports provider error: %s", provider_error)
                await app.bot.set_webhook(
                    url=expected,
                    allowed_updates=None,
                    secret_token=server.os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None,
                )
                await asyncio.sleep(3)
            except Exception as exc:
                last_error = str(exc)
                log.warning("Telegram reconnect attempt %s/6 failed: %s", attempt + 1, last_error)
                await asyncio.sleep(4)
        server.telegram_ready = False
        log.error("Telegram webhook reconnect failed after retries: %s", last_error or "provider error")

    server._initialize_integrations = wrapped
    server._netyar_telegram_reconnect_patch = True
    log.info("Telegram reconnect guard installed")
