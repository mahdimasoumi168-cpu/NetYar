"""Startup hardening for Telegram/Rubika integration registration.

Telegram is run with long polling by default. This avoids Railway edge-proxy
502 responses when Telegram cannot reach the public webhook reliably. Set
TELEGRAM_USE_WEBHOOK=true only when a stable public webhook endpoint is known.
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
        await asyncio.sleep(3)

        # Telegram: long polling is the reliable Railway mode. Webhook mode is
        # opt-in because Telegram's provider currently reports 502 against the
        # deployed public proxy even though the internal FastAPI health check is OK.
        try:
            import telegram_runtime as tg
            server.telegram_app = tg.build()
            await server.telegram_app.initialize()
            await server.telegram_app.start()

            use_webhook = server.os.getenv("TELEGRAM_USE_WEBHOOK", "false").strip().lower() in {
                "1", "true", "yes", "on"
            }
            if use_webhook:
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
                    raise RuntimeError(f"Telegram webhook registration failed: {last_error}")
            else:
                # Remove any stale webhook before polling. Do not drop pending
                # updates so messages sent during deployment are preserved.
                await server.telegram_app.bot.delete_webhook(drop_pending_updates=False)
                updater = getattr(server.telegram_app, "updater", None)
                if updater is None:
                    raise RuntimeError("python-telegram-bot updater is unavailable")
                await updater.start_polling(
                    allowed_updates=None,
                    drop_pending_updates=False,
                    close_loop=False,
                )
                server.telegram_ready = True
                server.log.info("Telegram long polling started successfully")
        except Exception:
            server.log.exception("Telegram startup failed")
            server.telegram_ready = False
            global_error = True

        # Rubika remains webhook-first; its existing polling fallback is kept.
        try:
            import rubika_v2 as rb
            server._patch_rubika(rb)
            endpoint = server.public_url("/rubika/receiveUpdate")
            last_error = None
            for attempt in range(10):
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
