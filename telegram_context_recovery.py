"""Context-preserving Telegram error recovery.

The important rule here is: a router returning ``None`` is NOT an error.
It means another handler still has a chance to own the update.  The previous
implementation turned that normal routing state into a visible error message,
which produced the user's bad UX: an error followed immediately by the real
prompt/success message.  This module now reports only genuine exceptions and
otherwise leaves routing alone.
"""
import logging
from telegram.ext import ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.context_recovery")


def _context_markup(B, uid, st):
    try:
        if st.get("partner_id") and st.get("partner_active", True):
            return B.partner_kb(st.get("lang", "fa"))
    except Exception:
        log.exception("partner context keyboard failed")
    try:
        if st.get("mode"):
            return B.cancel_kb(st.get("lang", "fa"))
    except Exception:
        log.exception("service context keyboard failed")
    return None


async def _recover_message(update, B, text="❌ یک خطای موقت رخ داد. اطلاعات مرحله فعلی حفظ شد؛ لطفاً دوباره تلاش کنید."):
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    user = getattr(update, "effective_user", None)
    if not message or not user:
        return
    st = B.S.setdefault(user.id, {})
    markup = _context_markup(B, user.id, st)
    kwargs = {"reply_markup": markup} if markup is not None else {}
    await message.reply_text(text, **kwargs)


async def _error_handler(update, context, B):
    # Genuine handler exceptions are handled here exactly once.  Normal
    # ApplicationHandlerStop / routing fall-through never reaches this path.
    if isinstance(context.error, ApplicationHandlerStop):
        return
    log.exception("Telegram unhandled update error", exc_info=context.error)
    try:
        await _recover_message(update, B)
    except Exception:
        log.exception("Telegram contextual recovery failed")


def install(app, B):
    if getattr(B, "_context_recovery_installed", False):
        return

    old_router = getattr(B, "router", None)
    if old_router is not None:
        async def guarded_router(update, context):
            uid = getattr(getattr(update, "effective_user", None), "id", None)
            try:
                result = old_router(update, context)
                if hasattr(result, "__await__"):
                    result = await result
                # IMPORTANT: None is a normal routing result.  Do not emit an
                # error here; the caller may legitimately continue to ptext,
                # service_text, or another feature handler.  Emitting a message
                # here was the root of the "error + prompt/success" duplicate UX.
                return result
            except ApplicationHandlerStop:
                raise
            except Exception:
                log.exception("contextual Telegram router recovery")
                if uid is not None:
                    try:
                        await _recover_message(update, B)
                    except Exception:
                        pass
                # Consume this failed route so older fallback routers cannot
                # execute the same action a second time after an exception.
                return True
        B.router = guarded_router

    app.add_error_handler(lambda update, context: _error_handler(update, context, B))
    B._context_recovery_installed = True
    log.info("Telegram context-preserving error recovery installed (no None-result error replies)")
