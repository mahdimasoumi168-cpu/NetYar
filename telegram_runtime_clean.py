"""Canonical Telegram runtime."""

import bot as B
import telegram_panels
import telegram_service_notifications
import telegram_ux_billing


def build():
    """Build Telegram and install the focused production extensions."""
    app = B.build()
    telegram_panels.install(app, B)
    telegram_service_notifications.install(app, B)
    telegram_ux_billing.install(app, B)
    return app
