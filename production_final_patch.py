"""Production final Telegram UI/callback patch."""
import logging
log = logging.getLogger("netyar.production_final")

# The original module imported CallbackQueryHandler from telegram, which is
# invalid for python-telegram-bot. Keep the implementation intact while using
# the correct public import location.

