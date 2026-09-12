"""Canonical Telegram runtime.

Telegram uses bot.py as the single customer/service implementation and small
focused modules for the richer partner/admin UI and manager notifications.
Legacy monkey-patch modules are intentionally not imported.
"""

import bot as B
import telegram_panels
import telegram_service_notifications


def build():
    """Build the canonical Telegram application and install focused extensions."""
    app = B.build()
    telegram_panels.install(app, B)
    telegram_service_notifications.install(app, B)
    return app
