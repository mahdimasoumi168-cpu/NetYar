"""Robust partner-code request bridge.

The original workflow assumed requests.user_id was always a partner id. That is
not true for customer-created requests. This layer resolves actual active
partner records and their current Telegram chat bindings, then stores the
pending request per partner so the reply can be routed back to admins.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("netyar.partner_code_fix")


def install():
    import bot as B
    if getattr(B, "_partner_code_fix_installed", False):
        return
    old_admin_cb = B.admin_cb

    async def admin_cb(update, context):
        q = update.callback_query
        data = str(q.data or "").split(":")
        if len(data) >= 3 and data[0] == "req" and data[1] == "p":
            if not B.admin(q.from_user.id):
                await q.answer("دسترسی ندارید")
                return
            try:
                rid = int(data[2])
            except (TypeError, ValueError):
                await q.answer("درخواست نامعتبر است")
                return
            req = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if not req:
                await q.answer("درخواست پیدا نشد")
                return

            # Prefer the partner that owns the request when requests were
            # created from the partner panel. Otherwise, use every active
            # partner with a known Telegram chat binding.
            partners = []
            try:
                p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (req["user_id"],)).fetchone()
                if p:
                    partners = [p]
            except Exception:
                log.exception("partner lookup by request owner failed")

            if not partners:
                partners = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id").fetchall()

            sent = 0
            for p in partners:
                chat_id = B.db.setting(f"partner_chat_{p['id']}", "")
                if not chat_id:
                    continue
                try:
                    B.db.set_setting(f"partner_code_request_{p['id']}", f"{rid}|{req['tracking_code']}")
                    await context.bot.send_message(
                        chat_id=int(chat_id),
                        text=(
                            "🔐 درخواست کد تأیید\n\n"
                            f"🎫 کد پیگیری: {req['tracking_code']}\n"
                            f"🧾 خدمت: {req['service_key']}\n\n"
                            "لطفاً کد/اطلاعات موردنیاز را همینجا ارسال کنید."
                        ),
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f"partner_code_cancel:{rid}")]]),
                    )
                    sent += 1
                except Exception:
                    log.exception("sending verification request to partner %s failed", p["id"])

            await q.answer("درخواست ارسال شد" if sent else "همکار فعال با چت ثبت‌شده پیدا نشد")
            if sent:
                return await q.message.reply_text(f"🔐 درخواست کد برای {sent} همکار ارسال شد.\n🎫 {req['tracking_code']}")
            return await q.message.reply_text(
                "❌ هیچ همکار فعالی که وارد پنل شده باشد پیدا نشد.\n"
                "از همکار بخواهید یک‌بار وارد پنل همکاران شود تا اتصال چت او ثبت شود."
            )
        return await old_admin_cb(update, context)

    B.admin_cb = admin_cb
    B._partner_code_fix_installed = True
    log.info("Partner verification-code routing fix installed")
