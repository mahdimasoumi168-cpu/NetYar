"""Startup hardening for Telegram/Rubika webhook registration."""
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

        try:
            import telegram_runtime as tg
            server.telegram_app = tg.build()
            await server.telegram_app.initialize()
            await server.telegram_app.start()
            tg_url = server.public_url("/telegram/update")
            secret = server.os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
            last_error = None
            for attempt in range(5):
                try:
                    await server.telegram_app.bot.set_webhook(
                        url=tg_url, allowed_updates=None, secret_token=secret
                    )
                    info = await server.telegram_app.bot.get_webhook_info()
                    if (info.url or "").rstrip("/") == tg_url.rstrip("/"):
                        server.telegram_ready = True
                        server.log.info(
                            "Telegram webhook registered: url_set=%s pending=%s last_error=%s",
                            bool(info.url), info.pending_update_count,
                            info.last_error_message or "none",
                        )
                        break
                    last_error = f"webhook URL mismatch: {info.url!r}"
                except Exception as exc:
                    last_error = str(exc)
                if attempt < 4:
                    await asyncio.sleep(3)
            else:
                server.telegram_ready = False
                server.log.error("Telegram webhook registration failed after retries: %s", last_error)
        except Exception:
            server.log.exception("Telegram webhook startup failed")
            server.telegram_ready = False
            global_error = True

        try:
            import rubika_v2 as rb
            server._patch_rubika(rb)
            endpoint = server.public_url("/rubika/update")
            last_error = None
            for attempt in range(3):
                try:
                    result = rb.call(
                        "updateBotEndpoints",
                        {"url": endpoint, "type": "ReceiveUpdate"},
                    )
                    server.log.info("Rubika ReceiveUpdate endpoint registration: %s", result)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < 2:
                        await asyncio.sleep(3)
            if last_error:
                raise RuntimeError(last_error)
            rb_info = rb.call("getMe")
            server.log.info(
                "Rubika getMe: bot_id=%s",
                ((rb_info.get("bot") or {}).get("bot_id") if isinstance(rb_info, dict) else "unknown"),
            )
            server.rubika_ready = True
        except Exception:
            server.log.exception("Rubika webhook registration failed")
            server.rubika_ready = False
            global_error = True

        if global_error:
            server.log.warning("One or more integrations are not ready; HTTP service remains healthy")

    server._initialize_integrations = initialize_with_retries
    server._netyar_integration_hardening = True
