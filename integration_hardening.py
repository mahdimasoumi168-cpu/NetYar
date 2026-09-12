"""Startup hardening for Telegram/Rubika webhook registration.

The Railway public proxy needs a short warm-up after a fresh deployment.
Rubika's ReceiveUpdate endpoint is registered on the conventional
/rubika/receiveUpdate path, which is also exposed by server.py.
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

        # Let Railway's public HTTPS proxy become reachable before providers
        # validate the webhook URL. This also reduces transient Telegram 502s.
        await asyncio.sleep(8)

        try:
            import telegram_runtime as tg
            server.telegram_app = tg.build()
            await server.telegram_app.initialize()
            await server.telegram_app.start()
            tg_url = server.public_url("/telegram/update")
            secret = server.os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
            last_error = None
            for attempt in range(8):
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
                if attempt < 7:
                    await asyncio.sleep(5)
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
            # Rubika's ReceiveUpdate webhook uses the conventional path. Keep
            # /rubika/update as an internal compatibility alias only.
            endpoint = server.public_url("/rubika/receiveUpdate")
            last_error = None
            for attempt in range(10):
                try:
                    result = rb.call(
                        "updateBotEndpoints",
                        {"url": endpoint, "type": "ReceiveUpdate"},
                    )
                    # rubika_v2.call normally unwraps data, but accept both
                    # response shapes so an API status is never misread.
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
                        "Rubika webhook registration attempt %s/10 failed: %s",
                        attempt + 1, last_error,
                    )
                    if attempt < 9:
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
