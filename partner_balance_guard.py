"""Partner balance guard for paid partner services.

A partner cannot start the government service when their available credit is
below the configured service price. The partner is sent back to the top-up
option instead of being allowed to submit work that cannot be paid for.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("netyar.partner_balance_guard")


def install(B):
    if getattr(B, "_partner_balance_guard_installed", False):
        return
    old_gov = B.gov

    async def guarded_gov(update, context):
        uid = update.effective_user.id
        st = B.S.get(uid, {})
        pid = st.get("partner_id")
        if pid:
            amount = int(B.db.setting("price_government", "500000") or 500000)
            p = B.db.conn.execute("SELECT name,balance,active FROM partners WHERE id=?", (pid,)).fetchone()
            balance = int(p["balance"] or 0) if p else 0
            if not p or not p["active"] or balance < amount:
                markup = B.kb([["➕ شارژ حساب"], ["💰 موجودی"], ["🚪 خروج از پنل"]])
                return await update.message.reply_text(
                    f"⛔ امکان ثبت این خدمت وجود ندارد.\n\n"
                    f"💰 هزینه خدمت: {amount:,} تومان\n"
                    f"💳 اعتبار فعلی شما: {balance:,} تومان\n\n"
                    "ابتدا حساب خود را به اندازه کافی شارژ کنید. "
                    "پس از تأیید شارژ توسط مدیریت، می‌توانید درخواست را ثبت کنید.",
                    reply_markup=markup,
                )
        return await old_gov(update, context)

    B.gov = guarded_gov
    B._partner_balance_guard_installed = True
    log.info("partner balance guard installed")
