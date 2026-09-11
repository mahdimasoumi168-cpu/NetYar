"""Startup hardening for Telegram/Rubika webhook registration.

Keep integration startup isolated from the core bot code. The public Railway
proxy can take a few seconds to become reachable after a new container starts,
so both providers are registered with bounded retries. Rubika's API can return
an InvalidUrl result without raising an exception; that result must be treated
as a failed registration and retried.
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

        # Railway's public proxy may not be ready at the exact moment the
        # application process starts. Give it a short warm-up before webhook
        # registration, without blocking the HTTP server itself.
        await asyncio.sleep(2)

        try:
            import telegram_runtime as tg
            server.telegram_app = tg.build()
            await server.telegram_app.initialize()
            await server.telegram_app.start()
            tg_url = server.public_url("/telegram/update")
            secret = server.os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
            last_error = None
            for attempt in range(6):
                try:
                    await server.telegram_app.bot.set_webhook(
                        url=tg_url, allowed_updates=None, secret_token=secret
                    )
                    info = await server.telegram_app.bot.get_webhook_info()
                    actual = (info.url or "").rstrip("/")
                    if actual == tg_url.rstrip("/"):
                        server.telegram_ready = True
                        server.log.info(
                            "Telegram webhook registered: url_set=%s pending=%s last_error=%s attempt=%s",
                            bool(info.url), info.pending_update_count,
                            info.last_error_message or "none", attempt + 1,
                        )
                        break
                    last_error = f"webhook URL mismatch: {info.url!r}"
                except Exception as exc:
                    last_error = str(exc)
                if attempt < 5:
                    await asyncio.sleep(4)
            else:
                server.telegram_ready = False
                server.log.error(
                    "Telegram webhook registration failed after retries: %s", last_error
                )
        except Exception:
            server.log.exception("Telegram webhook startup failed")
            server.telegram_ready = False
            global_error = True

        try:
            import rubika_v2 as rb
            server._patch_rubika(rb)
            endpoint = server.public_url("/rubika/update")
            last_error = None
            for attempt in range(7):
                try:
                    result = rb.call(
                        "updateBotEndpoints",
                        {"url": endpoint, "type": "ReceiveUpdate"},
                    )
                    # Rubika may return an error object with HTTP 200 instead
                    # of raising. Never mark the integration ready for one of
                    # those responses.
                    status = str(result.get("status", "")).strip().lower() if isinstance(result, dict) else ""
                    if status and status not in {"ok", "success", "true", "1"}:
                        raise RuntimeError(f"Rubika endpoint registration returned status={result.get('status')!r}")
                    server.log.info(
                        "Rubika ReceiveUpdate endpoint registration: %s | attempt=%s",
                        result, attempt + 1,
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = str(exc)
                    server.log.warning(
                        "Rubika webhook registration attempt %s/7 failed: %s",
                        attempt + 1, last_error,
                    )
                    if attempt < 6:
                        await asyncio.sleep(5)
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
