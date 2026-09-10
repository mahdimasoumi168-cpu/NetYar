"""Runtime hardening for webhook/button handling.

Rubika button clicks can contain both stale visible text and a stable
aux_data.button_id. The button id must win, otherwise the bot receives the
label (for example "🪪 ...") while the state machine expects the numeric id.
"""
import asyncio
import json
import logging

log = logging.getLogger("netyar.server_patch")


def _button_id_from_message(message):
    if not isinstance(message, dict):
        return ""
    aux = message.get("aux_data")
    if isinstance(aux, str):
        try:
            aux = json.loads(aux)
        except Exception:
            aux = None
    if isinstance(aux, dict):
        for key in ("button_id", "buttonId", "callback_data"):
            value = aux.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    for key in ("button_id", "buttonId", "callback_data"):
        value = message.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def install():
    import server
    if getattr(server, "_netyar_server_patch_installed", False):
        return

    def rb_text(update):
        u = server._rubika_inner(update)
        m = server._rubika_message(u)
        # Stable callback id first. This is the critical Rubika button fix.
        bid = _button_id_from_message(m)
        if bid:
            return bid
        if isinstance(m, dict):
            for key in ("text", "button_text"):
                if m.get(key):
                    return str(m[key]).strip()
        return ""

    server._rubika_text = rb_text

    # rubika_v2.process() has its own text parser, so patch that parser too.
    try:
        import rubika_v2 as rb

        def rb_v2_text_of(u):
            m = u.get("message") or u.get("new_message") or u
            if not isinstance(m, dict):
                return ""
            bid = _button_id_from_message(m)
            if bid:
                return bid
            for key in ("text", "button_text"):
                if m.get(key):
                    return str(m[key]).strip()
            return ""

        rb.text_of = rb_v2_text_of
    except Exception:
        log.exception("Could not patch Rubika text parser")

    # When a numeric Rubika button id is received, preserve the numeric id in
    # message.text. rubika_v2.handle() already understands numeric menu ids.
    def normalize_rubika_button(update, rb):
        raw = rb_text(update)
        if raw not in {str(i) for i in range(10)}:
            return update
        m = server._rubika_message(update)
        if isinstance(m, dict):
            m["text"] = raw
        return update

    server._normalize_rubika_button = normalize_rubika_button

    async def watchdog():
        while True:
            try:
                await asyncio.sleep(90)
                # Telegram: repair only when the configured URL actually differs.
                if server.telegram_app is not None:
                    try:
                        info = await server.telegram_app.bot.get_webhook_info()
                        expected = server.public_url("/telegram/update")
                        actual = (info.url or "").rstrip("/")
                        if actual != expected.rstrip("/"):
                            secret = server.os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
                            await server.telegram_app.bot.set_webhook(
                                url=expected, allowed_updates=None, secret_token=secret
                            )
                        server.telegram_ready = True
                    except Exception:
                        server.telegram_ready = False
                        log.exception("Telegram watchdog check failed")
                # Rubika is intentionally not re-registered here. Repeated
                # updateBotEndpoints calls were causing false InvalidUrl/outage
                # states even while POST /rubika/update was receiving updates.
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("watchdog failed")

    server._integration_watchdog = watchdog
    server._netyar_server_patch_installed = True
    log.info("NetYar server patch installed")
