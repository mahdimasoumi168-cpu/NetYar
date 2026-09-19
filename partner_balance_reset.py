"""One-click admin reset of all partner balances.

The reset is deliberately exposed as a protected Telegram admin command so
live balances are never changed accidentally by normal startup/deploy code.
"""
import logging
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.partner_balance_reset")
COMMAND = "🔴 صفر کردن موجودی همه همکاران"


def install(app, B):
    if getattr(B, "_partner_balance_reset_installed", False):
        return

    async def handler(update, context):
        # Permanently disabled: partner balances are durable business data and
        # must never be zeroed by a bot command.
        if not update.effective_user or not B.admin(update.effective_user.id):
            return
        if (update.message.text or "").strip() != COMMAND:
            return
        await update.message.reply_text(
            "⛔ این فرمان غیرفعال است. موجودی هیچ همکاری از طریق بات قابل صفر کردن نیست."
        )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-95)
    B._partner_balance_reset_installed = True
    log.info("partner balance reset command installed")
