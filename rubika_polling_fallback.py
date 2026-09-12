"""Rubika reliability fallback and production UI hardening."""
import asyncio
import logging
import os
import re

log = logging.getLogger("netyar.rubika_polling_fallback")


def normalize_phone(value):
    s = str(value or "").strip()
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def _inline_keypad(rows):
    """Convert the existing Rubika row format to an inline keypad.

    The old implementation used chat_keypad, which stays under the chat input.
    InlineKeypad is attached to the actual message, matching Telegram's UX.
    """
    return {
        "rows": [
            {
                "buttons": [
                    {"id": str(item[0]), "type": "Simple", "button_text": str(item[1])}
                    for item in (row or [])
                    if isinstance(item, (tuple, list)) and len(item) >= 2
                ]
            }
            for row in (rows or [])
            if row
        ]
    }


def _patch_rubika_inline_ui(rb):
    """Replace reply keypads with message-attached inline keypads.

    Also explicitly removes any legacy chat keypad so users do not retain the
    old persistent keyboard after upgrading.
    """
    if getattr(rb, "_netyar_inline_ui_installed", False):
        return

    def inline_send(chat, text, rows=None):
        payload = {
            "chat_id": str(chat),
            "text": str(text or ""),
            "chat_keypad_type": "Remove",
        }
        if rows:
            payload["inline_keypad"] = _inline_keypad(rows)
        return rb.call("sendMessage", payload)

    rb.send = inline_send
    rb._netyar_inline_ui_installed = True


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
        force_polling = os.getenv("RUBIKA_FORCE_POLLING", "0").strip().lower() in {"1", "true", "yes", "on"}
        if getattr(server, "rubika_ready", False) and not force_polling:
            return
        try:
            import rubika_v2 as rb
            rb.normalize_phone = normalize_phone
            server._patch_rubika(rb)
            _patch_rubika_inline_ui(rb)
            try:
                import rubika_admin_control_v5
                rubika_admin_control_v5.install()
                log.info("Rubika full admin control installed")
            except Exception:
                log.exception("Rubika full admin control could not be installed")
            task = getattr(server, "_rubika_polling_task", None)
            if task is None or task.done():
                server._rubika_polling_task = asyncio.create_task(_poll(server, rb))
            server.rubika_ready = True
            log.warning("Rubika is online with getUpdates polling fallback and inline UI")
        except Exception:
            server.rubika_ready = False
            log.exception("Could not start Rubika getUpdates fallback")

    server._initialize_integrations = initialize
    server._rubika_polling_fallback_installed = True
    log.info("Rubika polling fallback installed")
