"""Canonical Telegram runtime.

This module intentionally contains no monkey-patches.  Telegram uses the
handlers defined in bot.py directly so partner-panel buttons and service
routing have one authoritative implementation.
"""

import bot as B


def build():
    """Build the canonical python-telegram-bot application."""
    return B.build()
