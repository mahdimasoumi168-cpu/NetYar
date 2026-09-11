"""Compatibility shim for python-telegram-bot imports.

Some project patches import CallbackQueryHandler from the top-level
``telegram`` package, while the supported package exposes it from
``telegram.ext``. Keep the legacy patch code untouched and provide the
expected symbol before those patches are installed.
"""


def install():
    import telegram
    from telegram.ext import CallbackQueryHandler
    if not hasattr(telegram, "CallbackQueryHandler"):
        telegram.CallbackQueryHandler = CallbackQueryHandler
