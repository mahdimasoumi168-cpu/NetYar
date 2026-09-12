"""Final Telegram production guard.

Telegram is intentionally long-polling only. This guard is loaded last so
legacy webhook/watchdog patches cannot take Telegram out of polling mode.
It also makes /start deterministic after the large legacy patch stack.
"""
import os
import logging

log = logging.getLogger("netyar.server")


def install():
    import server
    import bot as B
    from telegram.ext import CommandHandler

    # Prevent legacy server code from selecting webhook mode.
    os.environ["TELEGRAM_USE_WEBHOOK"] = "false"

    # The project has accumulated many runtime patches which can wrap B.build.
    # Reinstall exactly one authoritative /start handler after all of them.
    old_build = getattr(B, "build", None)
    if old_build is not None and not getattr(B, "_netyar_polling_guard_build", False):
        def guarded_build():
            app = old_build()
            try:
                # Remove stale/duplicate /start handlers from group 0.
                for group, handlers in list(app.handlers.items()):
                    kept = []
                    for h in handlers:
                        if isinstance(h, CommandHandler) and "start" in set(h.commands):
                            continue
                        kept.append(h)
                    app.handlers[group] = kept
                # B.start is the final patched handler at this point.
                app.add_handler(CommandHandler("start", B.start), group=0)
                log.info("Telegram authoritative /start handler installed")
            except Exception:
                log.exception("Telegram /start handler installation failed")
            return app
        B.build = guarded_build
        B._netyar_polling_guard_build = True

    # python-telegram-bot requires error_callback to be a regular callable,
    # not a coroutine function. PTB schedules/handles the callback itself.
    def polling_error_callback(exc):
        log.error("Telegram polling error: %s", exc, exc_info=exc)

    async def polling_only_watchdog():
        while True:
            try:
                import asyncio
                await asyncio.sleep(90)
                if server.telegram_app is None:
                    continue
                await server.telegram_app.bot.delete_webhook(drop_pending_updates=False)
                # Do not manufacture readiness here. start_polling() is the
                # only place that is allowed to mark Telegram ready.
                log.info("Telegram polling watchdog: webhook remains disabled")
            except asyncio.CancelledError:
                return
            except Exception:
                server.log.exception("Telegram polling watchdog failed")

    server._telegram_polling_error_callback = polling_error_callback
    server._integration_watchdog = polling_only_watchdog
    server.log.info("Telegram polling-only guard installed")
