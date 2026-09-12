"""Rubika reliability fallback and production UI hardening."""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict

log = logging.getLogger("netyar.rubika_polling_fallback")

_RB_SEEN = OrderedDict()
_RB_SEEN_TTL = 120
_RB_NOTIFIED_REQUESTS = OrderedDict()
_RB_NOTIFY_TTL = 86400


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
    """Convert the existing Rubika row format to a message-attached inline keypad."""
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
    """Replace persistent reply keypads with inline keypads attached to messages."""
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


def _update_key(update):
    """Return a stable key for a Rubika update so retries cannot double-process it."""
    if not isinstance(update, dict):
        return ""
    u = update.get("update") if isinstance(update.get("update"), dict) else update
    msg = u.get("message") or u.get("new_message") or u.get("inline_message") or {}
    if not isinstance(msg, dict):
        msg = {}
    for key in ("message_id", "update_id", "id"):
        value = msg.get(key) or u.get(key)
        if value:
            return f"id:{value}"
    try:
        raw = json.dumps(update, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = repr(update)
    return "hash:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _seen_update(update):
    key = _update_key(update)
    if not key:
        return False
    now = time.monotonic()
    for k, ts in list(_RB_SEEN.items()):
        if now - ts > _RB_SEEN_TTL:
            _RB_SEEN.pop(k, None)
    if key in _RB_SEEN:
        return True
    _RB_SEEN[key] = now
    while len(_RB_SEEN) > 4096:
        _RB_SEEN.popitem(last=False)
    return False


def _notified_request(rid):
    now = time.monotonic()
    for k, ts in list(_RB_NOTIFIED_REQUESTS.items()):
        if now - ts > _RB_NOTIFY_TTL:
            _RB_NOTIFIED_REQUESTS.pop(k, None)
    if rid in _RB_NOTIFIED_REQUESTS:
        return True
    _RB_NOTIFIED_REQUESTS[rid] = now
    while len(_RB_NOTIFIED_REQUESTS) > 2048:
        _RB_NOTIFIED_REQUESTS.popitem(last=False)
    return False


def _rubika_request_snapshot(rb, uid):
    """Find the latest Rubika request for this external user before processing."""
    try:
        row = rb.db.conn.execute(
            "SELECT u.id AS user_id, r.id AS request_id "
            "FROM users u LEFT JOIN requests r ON r.user_id=u.id "
            "WHERE u.platform='rubika' AND u.external_id=? "
            "ORDER BY r.id DESC LIMIT 1",
            (str(uid),),
        ).fetchone()
        return int(row["request_id"]) if row and row["request_id"] is not None else 0
    except Exception:
        return 0


async def _notify_telegram_admins(server, rb, uid, before_request_id):
    """Forward a newly-created Rubika service request to Telegram managers."""
    try:
        bot = getattr(server, "telegram_app", None)
        if bot is None:
            return
        import bot as telegram_bot
        admin_ids = list(getattr(telegram_bot, "ADM", []) or [])
        if not admin_ids:
            return

        row = rb.db.conn.execute(
            "SELECT r.id,r.tracking_code,r.service_key,r.status,r.amount,r.created_at "
            "FROM requests r JOIN users u ON u.id=r.user_id "
            "WHERE u.platform='rubika' AND u.external_id=? AND r.id>? "
            "ORDER BY r.id DESC LIMIT 1",
            (str(uid), int(before_request_id or 0)),
        ).fetchone()
        if not row:
            return
        rid = int(row["id"])
        if _notified_request(rid):
            return

        text = (
            "👔 مدیر — درخواست جدید از روبیکا\n\n"
            f"🆕 درخواست خدمات ثبت شد\n"
            f"🎫 کد پیگیری: {row['tracking_code'] or '-'}\n"
            f"🛠 خدمت: {row['service_key'] or '-'}\n"
            f"📊 وضعیت: {row['status'] or '-'}\n"
            f"💰 مبلغ: {int(row['amount'] or 0):,} تومان\n"
            f"👤 شناسه روبیکا: {uid}\n\n"
            "📌 درخواست از روبیکا دریافت و برای پنل مدیریت تلگرام ارسال شد."
        )
        # Reuse the Telegram manager action buttons when available.
        markup = None
        try:
            from telegram_service_notifications import _admin_markup
            markup = _admin_markup(rid)
        except Exception:
            pass
        for aid in admin_ids:
            try:
                await bot.bot.send_message(chat_id=int(aid), text=text, reply_markup=markup)
            except Exception:
                log.exception("Failed to forward Rubika request %s to Telegram admin %s", rid, aid)
    except Exception:
        log.exception("Rubika-to-Telegram admin notification failed")


async def _poll(server, rb):
    offset_id = None
    log.warning("Rubika getUpdates fallback started")
    while True:
        try:
            payload = {"limit": 5}
            if offset_id:
                payload["offset_id"] = offset_id
            result = await asyncio.to_thread(rb.call, "getUpdates", payload)
            if not isinstance(result, dict):
                await asyncio.sleep(1)
                continue
            updates = result.get("updates") or []
            if not isinstance(updates, list):
                updates = []

            # Advance the Rubika offset immediately. Rubika documents that the
            # response's next_offset_id is used for the next getUpdates call.
            next_offset = result.get("next_offset_id")
            if next_offset:
                offset_id = str(next_offset)

            for update in updates:
                if not isinstance(update, dict) or _seen_update(update):
                    continue
                uid = None
                try:
                    uid = server._rubika_user(update)
                    before = _rubika_request_snapshot(rb, uid)
                    await server._run_rubika(update, rb)
                    await _notify_telegram_admins(server, rb, uid, before)
                except Exception:
                    log.exception("Rubika update processing failed: user=%s", uid)
                # Small pacing prevents a large backlog from appearing as a
                # burst of dozens/hundreds of messages in one moment.
                await asyncio.sleep(0.20)
            if not updates:
                await asyncio.sleep(0.8)
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
