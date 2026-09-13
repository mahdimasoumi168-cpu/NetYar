"""Context-preserving Telegram error recovery.

Never throws a user who is inside a service/partner flow back to the public
main menu after a transient routing/handler failure. The current per-user
state remains intact and the user receives the keyboard appropriate to the
current context.
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
        # During a service flow, keep the user in that flow. Cancel is safer
        # than rebuilding the public main menu and losing the active step.
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
                # A None result means the legacy router did not own the action.
                # Keep the current service/partner context instead of allowing
                # the absolute callback guard to fall back to B.main().
                if result is None and uid is not None:
                    st = B.S.setdefault(uid, {})
                    if st.get("partner_id") or st.get("mode"):
                        await _recover_message(update, B, "⛔ این گزینه فعلاً اجرا نشد. مرحله فعلی شما حفظ شده؛ لطفاً دوباره تلاش کنید.")
                        return True
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
                return True
        B.router = guarded_router

    app.add_error_handler(lambda update, context: _error_handler(update, context, B))
    B._context_recovery_installed = True
    log.info("Telegram context-preserving error recovery installed")
