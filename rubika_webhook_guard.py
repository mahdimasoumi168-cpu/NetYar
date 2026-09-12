"""Prevent Rubika webhook and getUpdates polling from processing the same update."""
import asyncio
import logging
from fastapi import Response

log = logging.getLogger("netyar.rubika.webhook_guard")


def install():
    import server
    if getattr(server, "_netyar_rubika_webhook_guard", False):
        return

    def polling_active():
        task = getattr(server, "_rubika_polling_task", None)
        return task is not None and not task.done()

    for route in list(server.api.routes):
        path = getattr(route, "path", "")
        if path not in {"/rubika/update", "/rubika/receiveUpdate"}:
            continue
        original = route.endpoint
        if getattr(original, "_netyar_polling_guarded", False):
            continue

        async def guarded(request, _original=original):
            if polling_active():
                # Polling is the single source of truth. The webhook endpoint
                # remains reachable for Rubika validation/health checks but
                # never processes an update while polling is active.
                return {"ok": True, "mode": "polling"}
            return await _original(request)

        guarded._netyar_polling_guarded = True
        route.endpoint = guarded

    server._netyar_rubika_webhook_guard = True
    log.info("Rubika webhook processing disabled while single polling task is active")
