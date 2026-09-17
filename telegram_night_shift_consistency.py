"""Single night-policy bridge for the live Telegram runtime.

The project contains several historical hours/night guards. This module makes
all known Telegram night predicates follow telegram_offhours_partner_gate_v2,
then installs the existing night-worker UI so its callbacks are actually live.
"""
import logging
log = logging.getLogger("netyar.night_consistency")


def install(app, B):
    try:
        from telegram_offhours_partner_gate_v2 import _is_open
    except Exception:
        log.exception("canonical off-hours gate unavailable")
        return False

    # Make the legacy night-worker module use the same persistent switch.
    try:
        import telegram_night_shift_v2 as N
        N.open_now = lambda: bool(_is_open(B))
        old_closed = getattr(N, "closed", None)
        if old_closed:
            def closed():
                return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
                        "🕖 ساعت کاری عادی: ۷ صبح تا ۷ شب به وقت تهران\n\n"
                        "فقط همکاران فعال در شیفت شب اجازه ورود و فعالیت دارند.")
            N.closed = closed
        if not getattr(B, "_night_shift_v2", False):
            N.install(app, B)
        log.info("NIGHT POLICY: telegram_night_shift_v2 synchronized")
    except Exception:
        log.exception("night-worker UI synchronization failed")
        return False

    # Historical guards must not bypass the administrator's global night switch.
    for name in ("telegram_business_hours_guard", "telegram_absolute_offhours_guard"):
        try:
            M = __import__(name)
            M.is_open = lambda *args, _B=B, **kwargs: bool(_is_open(_B))
            log.info("NIGHT POLICY: patched %s.is_open", name)
        except Exception:
            log.exception("night policy patch failed: %s", name)

    # Other old layers sometimes expose open_now/is_open predicates.
    for name in ("telegram_final_control", "telegram_night_shift", "telegram_night_shift_access", "telegram_night_shift_stability_v26"):
        try:
            M = __import__(name)
            if hasattr(M, "open_now"):
                M.open_now = lambda *args, _B=B, **kwargs: bool(_is_open(_B))
            if hasattr(M, "is_open"):
                M.is_open = lambda *args, _B=B, **kwargs: bool(_is_open(_B))
        except Exception:
            pass

    B._night_policy_consistency_v1 = True
    return True
