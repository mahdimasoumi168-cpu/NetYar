"""Rubika reliability fallback.

If Rubika rejects the Railway webhook URL with InvalidUrl, keep the bot alive
using the official getUpdates long-polling API instead of marking Rubika offline.
"""
import asyncio
import logging
import os

log = logging.getLogger("netyar.rubika_polling_fallback")


async def _poll(server, rb):
    offset_id = None
    log.warning("Rubika getUpdates fallback started")
    while True:
        try:
            payload = {"limit": 20}
            if offset_id:
                payload["offset_id"] = offset_id
            result = await asyncio.to_thread(rb.call, "getUpdates", payload)
            if not isinstance(result, dict):
                await asyncio.sleep(1)
                continue
            updates = result.get("updates") or []
            if not isinstance(updates, list):
                updates = []
            next_offset = result.get("next_offset_id")
            if next_offset:
                offset_id = str(next_offset)
            for update in updates:
                if isinstance(update, dict):
                    await server._run_rubika(update, rb)
            if not updates:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Rubika getUpdates fallback failed")
            await asyncio.sleep(3)


def install():
    import server
    if getattr(server, "_rubika_polling_fallback_installed", False):
        return
    original = server._initialize_integrations

    async def initialize():
        await original()
        # RUBIKA_FORCE_POLLING is used when the provider rejects the public
        # Railway endpoint. It deliberately takes precedence over the
        # webhook success flag from the older initializer.
        force_polling = os.getenv("RUBIKA_FORCE_POLLING", "0").strip().lower() in {"1", "true", "yes", "on"}
        if getattr(server, "rubika_ready", False) and not force_polling:
            return
        try:
            import rubika_v2 as rb
            server._patch_rubika(rb)
            task = getattr(server, "_rubika_polling_task", None)
            if task is None or task.done():
                server._rubika_polling_task = asyncio.create_task(_poll(server, rb))
            server.rubika_ready = True
            log.warning("Rubika is online with getUpdates polling fallback")
        except Exception:
            server.rubika_ready = False
            log.exception("Could not start Rubika getUpdates fallback")

    server._initialize_integrations = initialize
    server._rubika_polling_fallback_installed = True
    log.info("Rubika polling fallback installed")
