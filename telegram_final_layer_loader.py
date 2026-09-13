"""Deterministic loader for final Telegram layers.

The previous implementation scheduled async installers as background tasks. That
created a startup race: polling could receive the first update before the final
handlers were registered. These installers perform registration synchronously
inside their coroutine bodies, so drive them to completion immediately.
"""
import inspect


def _install_sync(installer, app, B):
    result = installer(app, B)
    if not inspect.iscoroutine(result):
        return result
    try:
        result.send(None)
    except StopIteration as done:
        return done.value
    raise RuntimeError("Final Telegram installer yielded during synchronous bootstrap")


def install(app, B):
    import telegram_final_admin_navigation_v3 as N
    import telegram_final_text_editor_v2 as E
    _install_sync(N.install, app, B)
    _install_sync(E.install, app, B)

    # Final partner-management communication layers. These were present in the
    # repository but were not previously owned by the deterministic loader,
    # allowing the legacy router to answer "option unavailable".
    try:
        import telegram_partner_ticket_fix as PT
        PT.install(B)
    except Exception:
        import logging
        logging.getLogger("netyar.telegram.final_layer_loader").exception("partner ticket fix unavailable")

    try:
        import telegram_ticket_reliability as TR
        _install_sync(TR.install, app, B)
    except Exception:
        import logging
        logging.getLogger("netyar.telegram.final_layer_loader").exception("ticket reliability unavailable")

    try:
        import telegram_ticket_media as TM
        TM.install(app, B)
    except Exception:
        import logging
        logging.getLogger("netyar.telegram.final_layer_loader").exception("ticket media unavailable")

    return True
