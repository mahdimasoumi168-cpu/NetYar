"""Serialize Rubika updates per user to avoid state races and delayed replies."""
import asyncio

_LOCKS = {}


def lock_for(user_id):
    key = str(user_id or "unknown")
    lock = _LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[key] = lock
    return lock
