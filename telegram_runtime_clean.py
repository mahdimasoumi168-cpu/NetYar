"""Canonical Telegram runtime."""

import bot as B
import telegram_panels
import telegram_service_notifications
import telegram_ux_billing
import telegram_admin_plus
import telegram_admin_entry
import telegram_residence_booklet


def build():
    """Build Telegram and install the focused production extensions."""
    app = B.build()
    telegram_panels.install(app, B)
    telegram_service_notifications.install(app, B)
    telegram_ux_billing.install(app, B)
    telegram_admin_plus.install(app, B)
    telegram_admin_entry.install(app, B)
    telegram_residence_booklet.install(app, B)
    return app
