"""Single night-policy bridge for the live Telegram runtime.

Public/customer availability is controlled only by business hours.
The night switch controls whether explicitly whitelisted night workers may
enter outside those hours. This keeps the two concepts separate and prevents
an enabled night switch from accidentally opening customer services.
"""
import logging
log = logging.getLogger("netyar.night_consistency")


def install(app, B):
    try:
        from telegram_offhours_partner_gate_v2 import _is_open, _clock_is_open, night_shift_enabled
    except Exception:
        log.exception("canonical off-hours gate unavailable")
        return False

    try:
        import telegram_night_shift_v2 as N
        old_allowed = getattr(N, "allowed", None)
        N.open_now = lambda: bool(_clock_is_open(B))
        if callable(old_allowed):
            def allowed(B_, uid, update=None):
                try:
                    if B_.admin(uid):
                        return True
                except Exception:
                    pass
                if not night_shift_enabled(B_):
                    return False
                try:
                    return bool(old_allowed(B_, uid, update))
                except Exception:
                    return False
            N.allowed = allowed
        old_closed = getattr(N, "closed", None)
        if old_closed:
            def closed():
                return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
                        "🕖 ساعت کاری عادی: ۷ صبح تا ۷ شب به وقت تهران\n\n"
                        "فقط همکاران فعال در شیفت شب و مجاز از طرف مدیریت اجازه ورود دارند.")
            N.closed = closed
        if not getattr(B, "_night_shift_v2", False):
            N.install(app, B)
        log.info("NIGHT POLICY: worker UI synchronized; public gate remains clock-only")
    except Exception:
        log.exception("night-worker UI synchronization failed")
        return False

    # Historical public gates must remain clock-only. Night workers are handled
    # by the dedicated partner gate above rather than by opening public services.
    for name in ("telegram_business_hours_guard", "telegram_absolute_offhours_guard"):
        try:
            M = __import__(name)
            M.is_open = lambda *args, _B=B, **kwargs: bool(_clock_is_open(_B))
            log.info("NIGHT POLICY: patched %s.is_open", name)
        except Exception:
            log.exception("night policy patch failed: %s", name)

    for name in ("telegram_final_control", "telegram_night_shift", "telegram_night_shift_access", "telegram_night_shift_stability_v26"):
        try:
            M = __import__(name)
            if hasattr(M, "open_now"):
                M.open_now = lambda *args, _B=B, **kwargs: bool(_clock_is_open(_B))
            if hasattr(M, "is_open"):
                M.is_open = lambda *args, _B=B, **kwargs: bool(_clock_is_open(_B))
        except Exception:
            pass

    B._night_policy_consistency_v2 = True
    return True
