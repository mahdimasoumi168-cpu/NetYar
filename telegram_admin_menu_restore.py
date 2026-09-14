"""Restore the full Telegram admin menu after legacy admin wrappers are installed.

The full_admin_control layer historically replaced the richer admin_plus menu with
an older reply-keyboard menu.  admin_plus already owns the complete callback menu,
so expose that menu whenever the full admin layer asks for its admin keyboard.
"""
import logging

log = logging.getLogger("netyar.telegram.admin_menu_restore")


def install(app, B):
    try:
        import full_admin_control_patch as fac
    except Exception:
        log.exception("full admin control module unavailable")
        return

    if not callable(getattr(B, "amenu", None)):
        log.warning("B.amenu is not available; keeping existing admin menu")
        return

    def restored_menu(_B=None):
        try:
            return B.amenu()
        except Exception:
            log.exception("failed to build restored admin menu")
            return fac._admin_menu(B)

    fac._admin_menu = restored_menu
    B._admin_menu_restore_installed = True
    log.info("full Telegram admin menu restored")
