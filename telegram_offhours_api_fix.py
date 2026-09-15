"""Compatibility fix for the canonical Telegram off-hours gate.

This module does not replace the existing off-hours/partner flow. It only
normalizes configurable time values and exposes the public ``is_open`` helper
used by the night-shift logout guard. The original gate remains the owner of
access control and partner login.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tehran")
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
DEFAULT_OPEN = "07:00"
DEFAULT_CLOSE = "19:00"


def _normalize_time(value, default):
    value = str(value or default).strip().translate(DIGITS)
    # Accept HH:MM and HH:MM:SS; time.fromisoformat validates the range.
    try:
        parsed = time.fromisoformat(value)
        return parsed.strftime("%H:%M")
    except Exception:
        return default


def install(app, B):
    try:
        import telegram_offhours_partner_gate_v2 as gate
    except Exception:
        return False

    def setting(B0, key, default):
        try:
            raw = B0.db.setting(key, default)
        except Exception:
            raw = default
        return _normalize_time(raw, default) if key in {"work_open", "work_close"} else str(raw or default)

    def is_open(B0):
        opening = setting(B0, "work_open", DEFAULT_OPEN)
        closing = setting(B0, "work_close", DEFAULT_CLOSE)
        try:
            opened = time.fromisoformat(opening)
            closed = time.fromisoformat(closing)
            now = datetime.now(TZ).time()
            return opened <= now < closed if opened < closed else (now >= opened or now < closed)
        except Exception:
            # Fail closed on an invalid configuration.
            return False

    gate._setting = setting
    gate._is_open = is_open
    gate.is_open = is_open
    B._offhours_api_fix_v1 = True
    return True
