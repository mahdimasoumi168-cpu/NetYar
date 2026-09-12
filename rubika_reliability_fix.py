"""Rubika production reliability layer.

Keeps the existing business handlers, but removes long blocking HTTP waits and
processes a batch of updates concurrently so one slow request cannot stall the
whole Rubika bot.
"""
import asyncio
import json
import logging
import os
import time
import requests

log = logging.getLogger("netyar.rubika.reliability")


def _fast_call_factory(rb):
    def fast_call(method, payload=None):
        timeout = 10 if method == "getUpdates" else 12
        last = None
        for attempt in range(2):
            try:
                r = rb.HTTP.post(f"{rb.BASE}/{method}", json=payload or {}, timeout=timeout)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict) and data.get("status") not in (None, "OK"):
                    raise RuntimeError(str(data))
                return data.get("data", data) if isinstance(data, dict) else data
            except (requests.RequestException, RuntimeError) as exc:
                last = exc
                if attempt == 0:
                    time.sleep(0.15)
        raise last or RuntimeError(f"Rubika {method} failed")
    return fast_call


async def _process_one(server, rb, update):
    uid = None
    try:
        uid = server._rubika_user(update)
        before = 0
        try:
            # Keep the existing snapshot helper when available.
            import rubika_polling_fallback as pf
            before = pf._rubika_request_snapshot(rb, uid)
        except Exception:
            pass
        await server._run_rubika(update, rb)
        try:
            import rubika_polling_fallback as pf
            await pf._notify_telegram_admins(server, rb, uid, before)
        except Exception:
            log.exception("Rubika admin notification failed")
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Rubika update failed: user=%s", uid)


async def _fast_poll(server, rb):
    offset_id = None
    sem = asyncio.Semaphore(8)
    log.warning("Rubika fast polling started")

    async def limited(update):
        async with sem:
            await _process_one(server, rb, update)

    while True:
        try:
            payload = {"limit": 20}
            if offset_id:
                payload["offset_id"] = offset_id
            result = await asyncio.to_thread(rb.call, "getUpdates", payload)
            if not isinstance(result, dict):
                await asyncio.sleep(0.05)
                continue
            updates = result.get("updates") or []
            nxt = result.get("next_offset_id")
            if nxt:
                offset_id = str(nxt)
            clean = []
            try:
                import rubika_polling_fallback as pf
                for u in updates:
                    if isinstance(u, dict) and not pf._seen_update(u, server):
                        clean.append(u)
            except Exception:
                clean = [u for u in updates if isinstance(u, dict)]
            if clean:
                await asyncio.gather(*(limited(u) for u in clean), return_exceptions=True)
            else:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Rubika fast polling error")
            await asyncio.sleep(0.5)


def install():
    import server
    if getattr(server, "_rubika_reliability_fix_installed", False):
        return
    original_initialize = server._initialize_integrations

    async def initialize():
        await original_initialize()
        try:
            import rubika_v2 as rb
            rb.call = _fast_call_factory(rb)
            old_task = getattr(server, "_rubika_polling_task", None)
            if old_task is not None and not old_task.done():
                old_task.cancel()
                try:
                    await old_task
                except asyncio.CancelledError:
                    pass
            server._rubika_polling_task = asyncio.create_task(_fast_poll(server, rb))
            server.rubika_ready = True
            log.warning("Rubika reliability layer active")
        except Exception:
            log.exception("Rubika reliability layer could not start")

    server._initialize_integrations = initialize
    server._rubika_reliability_fix_installed = True
