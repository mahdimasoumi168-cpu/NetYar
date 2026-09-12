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
        if not update.effective_user or not B.admin(update.effective_user.id):
            return
        if (update.message.text or "").strip() != COMMAND:
            return
        rows = B.db.conn.execute("SELECT id,balance FROM partners").fetchall()
        total = len(rows)
        old_total = sum(int(r["balance"] or 0) for r in rows)
        B.db.conn.execute("UPDATE partners SET balance=0,updated_at=?", (B.now(),))
        B.db.audit("telegram", update.effective_user.id, "reset_partner_balances", "all", f"count={total};old_total={old_total}")
        B.db.conn.commit()
        await update.message.reply_text(
            f"✅ موجودی همه همکاران صفر شد.\n\n👥 تعداد همکاران: {total}\n💰 مجموع اعتبار قبلی: {old_total:,} تومان\n💳 موجودی فعلی همه: ۰ تومان\n\nاز این لحظه برای انجام خدمت، همکار باید ابتدا حساب خود را شارژ کند و درخواست شارژ توسط مدیریت تأیید شود."
        )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-95)
    B._partner_balance_reset_installed = True
    log.info("partner balance reset command installed")
