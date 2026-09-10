"""Final safety fixes that must run after the business-flow layer.

Keeps the production top-up callback compatible with the existing admin
callback parser while preserving the currently working Telegram/Rubika flows.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("netyar.final_safety_patch")


def install():
    import bot as B
    if getattr(B, "_final_safety_patch_installed", False):
        return

    old_media = B.media

    async def media(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})

        # business_flow_patch previously emitted a 4-part top-up callback,
        # while the production admin handler expects the topup row id too.
        # Handle the receipt here with the canonical 5-part callback format.
        if st.get("mode") == "topup_receipt":
            msg = update.message
            fid = (msg.photo[-1].file_id if msg.photo else
                   (msg.document.file_id if msg.document else ""))
            if not fid:
                return await msg.reply_text(
                    "❌ لطفاً تصویر یا فایل رسید را ارسال کنید.",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )

            pid = st.get("partner_id")
            amount = int(st.get("topup_amount") or 0)
            p = B.db.conn.execute(
                "SELECT * FROM partners WHERE id=? AND active=1", (pid,)
            ).fetchone()
            if not p or amount <= 0:
                st["mode"] = None
                st.pop("topup_amount", None)
                return await msg.reply_text(
                    "❌ درخواست شارژ پیدا نشد. لطفاً دوباره از پنل همکاران اقدام کنید.",
                    reply_markup=B.partner_kb(st.get("lang", "fa")),
                )

            cur = B.db.conn.execute(
                "INSERT INTO topups(partner_id,amount,receipt_file_id,status,created_at) VALUES(?,?,?,?,?)",
                (pid, amount, fid, "pending", B.now()),
            )
            topup_id = cur.lastrowid
            B.db.conn.commit()

            st["mode"] = None
            st.pop("topup_amount", None)

            mk = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "✅ تأیید شارژ",
                    callback_data=f"tu:a:{pid}:{amount}:{topup_id}",
                ),
                InlineKeyboardButton(
                    "❌ رد شارژ",
                    callback_data=f"tu:r:{pid}:{amount}:{topup_id}",
                ),
            ]])

            text = (
                "💰 درخواست شارژ حساب\n"
                f"👤 {p['name']}\n"
                f"📱 {p['phone']}\n"
                f"💵 مبلغ: {amount:,} تومان\n"
                f"🎫 شناسه شارژ: {topup_id}\n"
                "📎 رسید پیوست شده است."
            )
            for aid in B.ADM:
                try:
                    await context.bot.send_message(
                        chat_id=int(aid), text=text, reply_markup=mk
                    )
                    if msg.photo:
                        await context.bot.send_photo(
                            chat_id=int(aid), photo=fid,
                            caption=f"📎 رسید شارژ {topup_id}",
                        )
                    elif msg.document:
                        await context.bot.send_document(
                            chat_id=int(aid), document=fid,
                            caption=f"📎 رسید شارژ {topup_id}",
                        )
                except Exception:
                    log.exception("failed to forward topup receipt")

            return await msg.reply_text(
                "✅ رسید شما دریافت شد و همراه با درخواست شارژ برای مدیریت ارسال شد.\n"
                "پس از تأیید مدیریت، موجودی شما افزایش پیدا می‌کند.",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )

        return await old_media(update, context)

    B.media = media
    B._final_safety_patch_installed = True
    log.info("final safety patch installed")
