"""Final Rubika hardening layer.

Installed before the reliability initializer. It fixes two recurring production
failure modes: valid repeated button clicks being discarded by semantic
fingerprinting, and inline keyboards being dropped when legacy row formats are
passed to the final send boundary.
"""
import asyncio
import logging
import time
from collections import OrderedDict

log = logging.getLogger("netyar.rubika.final_hardening")


def _rows_to_inline(rows, fa=False, translate=None):
    out = []
    for row in rows or []:
        buttons = []
        for index, item in enumerate(row or []):
            bid = None
            label = None
            if isinstance(item, dict):
                bid = item.get("id") or item.get("button_id")
                label = item.get("button_text") or item.get("text") or item.get("label")
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                bid, label = item[0], item[1]
            if bid is None:
                bid = str(index)
            if label is None:
                label = str(item)
            label = str(label)
            if fa and translate:
                label = translate(label)
            buttons.append({"id": str(bid), "type": "Simple", "button_text": label})
        if buttons:
            out.append({"buttons": buttons})
    return {"rows": out}


def _patch_inline_ui(rb):
    if getattr(rb, "_netyar_final_inline_ui", False):
        return
    import rubika_polling_fallback as pf

    def inline_send(chat, text, rows=None):
        fa = pf._fa_mode(rb, chat)
        visible_text = pf._fa_ui_text(text) if fa else str(text or "")
        payload = {"chat_id": str(chat), "text": visible_text}
        if rows:
            payload["inline_keypad"] = _rows_to_inline(rows, fa=fa, translate=pf._fa_ui_text)
            # Do not send a legacy reply-keyboard payload together with an
            # inline keypad. Inline buttons remain attached to this message.
        else:
            # Explicitly remove any old reply keyboard when sending a plain
            # message, while leaving the inline-only UI policy intact.
            payload["chat_keypad_type"] = "Remove"
        return rb.call("sendMessage", payload)

    rb.send = inline_send
    rb._netyar_final_inline_ui = True


def _patch_polling(module):
    async def fast_poll(server, rb):
        offset_id = None
        semaphore = asyncio.Semaphore(12)
        locks = {}
        seen = OrderedDict()
        seen_ttl = 180.0
        log.warning("Rubika final single polling started")

        def already_seen(update):
            key = module._update_key(update)
            now = time.monotonic()
            for old_key, timestamp in list(seen.items()):
                if now - timestamp > seen_ttl:
                    seen.pop(old_key, None)
            if key and key in seen:
                return True
            if key:
                seen[key] = now
                while len(seen) > 4096:
                    seen.popitem(last=False)
            return False

        async def process_one(update):
            uid = None
            try:
                uid = server._rubika_user(update)
                lock = locks.setdefault(str(uid or "unknown"), asyncio.Lock())
                async with lock:
                    before = 0
                    try:
                        before = module._rubika_request_snapshot(rb, uid)
                    except Exception:
                        pass
                    await asyncio.to_thread(module._run_sync, server, update, rb)
                    try:
                        await module._notify_telegram_admins(server, rb, uid, before)
                    except Exception:
                        log.exception("Rubika admin notification failed: user=%s", uid)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Rubika update failed: user=%s", uid)

        while True:
            try:
                payload = {"limit": 20}
                if offset_id:
                    payload["offset_id"] = offset_id
                result = await asyncio.to_thread(rb.call, "getUpdates", payload)
                if not isinstance(result, dict):
                    await asyncio.sleep(0.1)
                    continue
                updates = result.get("updates") or []
                if not isinstance(updates, list):
                    updates = []
                clean = [u for u in updates if isinstance(u, dict) and not already_seen(u)]
                if clean:
                    await asyncio.gather(*(process_one(u) for u in clean), return_exceptions=True)
                # Advance only after this batch has been handed to the
                # per-user workers. This avoids losing a batch on processing
                # exceptions while keeping one active polling cursor.
                nxt = result.get("next_offset_id")
                if nxt:
                    offset_id = str(nxt)
                if not updates:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("Rubika final polling error")
                await asyncio.sleep(0.5)

    module._fast_poll = fast_poll


def install():
    import rubika_reliability_fix as reliability
    try:
        _patch_polling(reliability)
        import rubika_v2 as rb
        _patch_inline_ui(rb)
        log.info("Rubika final hardening installed")
    except Exception:
        log.exception("Rubika final hardening installation failed")
