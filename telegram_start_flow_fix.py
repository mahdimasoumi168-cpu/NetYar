"""Keep Telegram startup to one language prompt + normal main flow.

telegram_ux_billing historically wrapped B.start and sent a second
"دسترسی سریع" message. The canonical no-reply-keyboard layer already owns the
persistent restart button, so that wrapper only created an unwanted extra
startup message. Recover the original start callable from the wrapper closure.
"""
import inspect
import logging
log = logging.getLogger("netyar.telegram_start_flow")


def install(B):
    if getattr(B, "_telegram_start_flow_fixed", False):
        return
    current = getattr(B, "start", None)
    if current is None:
        return
    # telegram_ux_billing.start_with_restart closes over old_start.
    # Prefer a closure callable rather than guessing a module-specific name.
    try:
        for cell in (getattr(current, "__closure__", None) or ()):
            value = cell.cell_contents
            if inspect.iscoroutinefunction(value) and value is not current:
                B.start = value
                B._telegram_start_flow_fixed = True
                log.info("Removed duplicate quick-access startup wrapper")
                return
    except Exception:
        log.exception("Could not unwrap Telegram start wrapper")
