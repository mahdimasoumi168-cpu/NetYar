"""Stable startup for Telegram and Rubika integrations.

Telegram intentionally uses long polling in production. This avoids Railway
proxy/webhook failures and keeps Telegram independent from Rubika startup.
"""
import asyncio

from fastapi.responses import PlainTextResponse


def install():
    import server
    if getattr(server, "_netyar_integration_hardening", False):
        return

    @server.api.middleware("http")
    async def fast_rubika_probe(request, call_next):
        if request.method == "HEAD" and request.url.path in {
            "/rubika/receiveUpdate", "/rubika/update"
        }:
            return PlainTextResponse("OK", status_code=200)
        return await call_next(request)

    async def initialize_with_retries():
        global_error = False
        await asyncio.sleep(1)

        # Telegram: force long polling. Do not register a webhook here.
        # This also removes any stale webhook left by an older deployment.
        try:
            import telegram_runtime as tg
            server.telegram_app = tg.build()
            await server.telegram_app.initialize()
            await server.telegram_app.start()

            await server.telegram_app.bot.delete_webhook(drop_pending_updates=False)
            updater = getattr(server.telegram_app, "updater", None)
            if updater is None:
                raise RuntimeError("python-telegram-bot updater is unavailable")

            await updater.start_polling(allowed_updates=None)
            server.telegram_ready = True
            server.log.info("Telegram long polling started successfully")
        except Exception:
            server.log.exception("Telegram startup failed")
            server.telegram_ready = False
            global_error = True

        # Rubika is optional. Its webhook failure must never prevent Telegram.
        try:
            import rubika_v2 as rb
            server._patch_rubika(rb)
            endpoint = server.public_url("/rubika/receiveUpdate")
            last_error = None
            for attempt in range(3):
                try:
                    result = rb.call(
                        "updateBotEndpoints",
                        {"url": endpoint, "type": "ReceiveUpdate"},
                    )
                    status = ""
                    if isinstance(result, dict):
                        status = str(result.get("status", "") or "").strip().lower()
                        if not status and isinstance(result.get("data"), dict):
                            status = str(result["data"].get("status", "") or "").strip().lower()
                    if status and status not in {"ok", "success", "true", "1"}:
                        raise RuntimeError(
                            f"Rubika endpoint registration returned status={result.get('status')!r}"
                        )
                    server.log.info(
                        "Rubika ReceiveUpdate endpoint registered: url=%s result=%s attempt=%s",
                        endpoint, result, attempt + 1,
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = str(exc)
                    server.log.warning(
                        "Rubika webhook registration attempt %s/3 failed: %s",
                        attempt + 1, last_error,
                    )
                    if attempt < 2:
                        await asyncio.sleep(2)

            if last_error:
                raise RuntimeError(last_error)

            rb_info = rb.call("getMe")
            server.log.info(
                "Rubika getMe: bot_id=%s",
                ((rb_info.get("bot") or {}).get("bot_id") if isinstance(rb_info, dict) else "unknown"),
            )
            server.rubika_ready = True
        except Exception:
            # Rubika is deliberately isolated from Telegram startup.
            server.log.exception("Rubika startup failed; Telegram remains active")
            server.rubika_ready = False
            global_error = True

        if global_error:
            server.log.warning("One or more integrations are not ready; HTTP service remains healthy")

    server._initialize_integrations = initialize_with_retries
    server._netyar_integration_hardening = True
