"""Final Telegram production guard.

Telegram is intentionally long-polling only. This guard is loaded last so
legacy watchdogs cannot restore a webhook after startup.
"""
import os


def install():
    import server

    # Prevent legacy server code from selecting webhook mode.
    os.environ["TELEGRAM_USE_WEBHOOK"] = "false"

    async def polling_only_watchdog():
        while True:
            try:
                import asyncio
                await asyncio.sleep(90)
                if server.telegram_app is None:
                    continue
                # Never restore a webhook. If an old webhook somehow exists,
                # remove it and keep the polling process authoritative.
                await server.telegram_app.bot.delete_webhook(drop_pending_updates=False)
                server.telegram_ready = True
            except asyncio.CancelledError:
                return
            except Exception:
                server.log.exception("Telegram polling watchdog failed")

    server._integration_watchdog = polling_only_watchdog
    server.log.info("Telegram polling-only guard installed")
