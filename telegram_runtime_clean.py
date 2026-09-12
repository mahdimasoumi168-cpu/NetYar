"""Canonical Telegram runtime.

Telegram uses bot.py as the single customer/service implementation and the
separate telegram_panels module for the richer partner/admin UI. Legacy
monkey-patch modules are intentionally not imported.
"""

import bot as B
import telegram_panels


def build():
    """Build the canonical Telegram application and install panel handlers."""
    app = B.build()
    telegram_panels.install(app, B)
    return app
