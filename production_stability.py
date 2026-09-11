"""Final production stability guards.

This module is intentionally small and idempotent.  It does not replace the
existing business logic; it protects the shared routing/runtime seams from
common production failures while the older compatibility patches remain in
place.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Any

log = logging.getLogger("netyar.stability")

_MAX_SEEN_TELEGRAM = 2048
_SEEN_TELEGRAM: OrderedDict[int, float] = OrderedDict()
_USER_LOCKS: dict[tuple[str, str], asyncio.Lock] = {}


def _lock_for(platform: str, user_id: Any) -> asyncio.Lock:
    key = (platform, str(user_id))
    lock = _USER_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _USER_LOCKS[key] = lock
    return lock


def _mark_telegram_seen(update_id: Any) -> bool:
    if update_id is None:
        return False
    try:
        value = int(update_id)
    except (TypeError, ValueError):
        return False
    if value in _SEEN_TELEGRAM:
        _SEEN_TELEGRAM.move_to_end(value)
        return True
    _SEEN_TELEGRAM[value] = time.monotonic()
    while len(_SEEN_TELEGRAM) > _MAX_SEEN_TELEGRAM:
        _SEEN_TELEGRAM.popitem(last=False)
    return False


def _install_partner_callback_guard() -> None:
    import bot as B

    if getattr(B, "_netyar_partner_callback_guard", False):
        return

    old_router = B.router

    async def guarded_router(update, context):
        text = (getattr(getattr(update, "message", None), "text", "") or "").strip()
        result = await old_router(update, context)
        # The persistent callback adapter uses a None return value to decide
        # whether it should fall through to ptext/service_text.  The partner
        # button changes the state to p_phone and must never be reinterpreted
        # as the phone number itself.
        if text in {"👥 پنل همکاران", "پنل همکاران"}:
            return True
        return result

    B.router = guarded_router
    B._netyar_partner_callback_guard = True
    log.info("partner callback guard installed")


def _install_telegram_serialization() -> None:
    import server

    if getattr(server, "_netyar_telegram_stability_guard", False):
        return

    old_process = server._process_telegram_update

    async def guarded_process(update):
        update_id = getattr(update, "update_id", None)
        if _mark_telegram_seen(update_id):
            log.warning("duplicate Telegram update ignored: update_id=%s", update_id)
            return

        user_id = None
        try:
            user_id = update.effective_chat.id if update.effective_chat else None
        except Exception:
            user_id = None

        if user_id is None:
            return await old_process(update)

        lock = _lock_for("telegram", user_id)
        async with lock:
            await old_process(update)

    server._process_telegram_update = guarded_process
    server._netyar_telegram_stability_guard = True
    log.info("Telegram per-chat serialization guard installed")


def _install_rubika_serialization() -> None:
    import server

    if getattr(server, "_netyar_rubika_stability_guard", False):
        return

    old_run = server._run_rubika

    async def guarded_run(update, rb):
        try:
            user_id = server._rubika_user(update)
        except Exception:
            user_id = "unknown"
        lock = _lock_for("rubika", user_id)
        async with lock:
            await old_run(update, rb)

    server._run_rubika = guarded_run
    server._netyar_rubika_stability_guard = True
    log.info("Rubika per-user serialization guard installed")


def install() -> None:
    """Install every production guard exactly once."""
    if globals().get("_INSTALLED"):
        return

    _install_partner_callback_guard()
    _install_telegram_serialization()
    _install_rubika_serialization()
    globals()["_INSTALLED"] = True
    log.info("production stability guards installed")
