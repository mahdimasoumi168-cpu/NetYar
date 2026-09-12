"""Rubika production reliability layer.

Runs the synchronous Rubika business handler off the asyncio event loop,
keeps exactly one polling task, serializes each user's updates, and installs
the same UI/service hardening used by the legacy fallback.
"""
import asyncio
import logging
import requests
import time

log = logging.getLogger("netyar.rubika.reliability")


def _fast_call_factory(rb):
    def fast_call(method, payload=None):
        timeout = 8 if method == "getUpdates" else 10
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
                    time.sleep(0.1)
        raise last or RuntimeError(f"Rubika {method} failed")
    return fast_call


def _run_sync(server, update, rb):
    normalized = server._normalize_rubika_button(update, rb)
    rb.process(normalized)


async def _process_one(server, rb, update, locks):
    uid = None
    try:
        uid = server._rubika_user(update)
        lock = locks.setdefault(str(uid or "unknown"), asyncio.Lock())
        async with lock:
            before = 0
            try:
                import rubika_polling_fallback as pf
                before = pf._rubika_request_snapshot(rb, uid)
            except Exception:
                pass
            await asyncio.to_thread(_run_sync, server, update, rb)
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
    sem = asyncio.Semaphore(12)
    locks = {}
    log.warning("Rubika single fast polling started")

    async def limited(update):
        async with sem:
            await _process_one(server, rb, update, locks)

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
            await asyncio.sleep(0.3)


def _install_rubika_hardening(server, rb):
    server._patch_rubika(rb)
    try:
        import rubika_polling_fallback as pf
        rb.normalize_phone = pf.normalize_phone
        pf._patch_rubika_inline_ui(rb)
        log.info("Rubika inline UI and fallback hardening installed")
    except Exception:
        log.exception("Rubika inline UI hardening could not be installed")
    try:
        import partner_pricing
        partner_pricing.install_rubika(rb)
    except Exception:
        log.exception("Rubika partner pricing could not be installed")
    try:
        import rubika_iranian_complaints
        rubika_iranian_complaints.install(rb)
    except Exception:
        log.exception("Rubika Iranian UX could not be installed")
    try:
        import rubika_admin_control_v5
        rubika_admin_control_v5.install()
    except Exception:
        log.exception("Rubika admin controls could not be installed")


def install():
    import server
    if getattr(server, "_rubika_reliability_fix_installed", False):
        return

    original_initialize = server._initialize_integrations

    async def initialize():
        await original_initialize()
        try:
            import rubika_v2 as rb
            _install_rubika_hardening(server, rb)
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
            log.warning("Rubika single reliability polling layer active")
        except Exception:
            log.exception("Rubika reliability layer could not start")
            server.rubika_ready = False

    server._initialize_integrations = initialize
    server._rubika_reliability_fix_installed = True
