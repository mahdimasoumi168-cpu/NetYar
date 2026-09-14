"""Final safety fixes for Telegram partner top-ups and request routing."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.final_safety_patch")


def install():
    import bot as B
    if getattr(B, "_final_safety_patch_installed", False):
        return

    old_media = B.media

    async def media(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})

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
                InlineKeyboardButton("✅ تأیید شارژ", callback_data=f"tu:a:{pid}:{amount}:{topup_id}"),
                InlineKeyboardButton("❌ رد شارژ", callback_data=f"tu:r:{pid}:{amount}:{topup_id}"),
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
                    await context.bot.send_message(chat_id=int(aid), text=text, reply_markup=mk)
                    if msg.photo:
                        await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"📎 رسید شارژ {topup_id}")
                    elif msg.document:
                        await context.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 رسید شارژ {topup_id}")
                except Exception:
                    log.exception("failed to forward topup receipt")

            return await msg.reply_text(
                "✅ رسید شما دریافت شد و همراه با درخواست شارژ برای مدیریت ارسال شد.\n"
                "پس از تأیید مدیریت، موجودی شما افزایش پیدا می‌کند.",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )

        return await old_media(update, context)

    async def topup_callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        parts = str(q.data or "").split(":")
        if len(parts) not in (4, 5) or parts[0] != "tu" or parts[1] not in {"a", "r"}:
            return

        await q.answer()
        action = parts[1]
        try:
            pid = int(parts[2])
            if len(parts) == 5:
                callback_amount = int(parts[3])
                topup_id = int(parts[4])
            else:
                callback_amount = 0
                topup_id = int(parts[3])
        except (TypeError, ValueError):
            await q.message.reply_text("❌ شناسه شارژ نامعتبر است.")
            raise ApplicationHandlerStop

        row = B.db.conn.execute("SELECT * FROM topups WHERE id=?", (topup_id,)).fetchone()
        if not row:
            await q.message.reply_text("❌ درخواست شارژ پیدا نشد.")
            raise ApplicationHandlerStop
        if int(row["partner_id"]) != pid:
            await q.message.reply_text("❌ اطلاعات درخواست شارژ با هم تطابق ندارد.")
            raise ApplicationHandlerStop

        real_amount = int(row["amount"] or 0)
        if callback_amount and callback_amount != real_amount:
            await q.message.reply_text("❌ مبلغ درخواست با مبلغ ثبت‌شده تطابق ندارد.")
            raise ApplicationHandlerStop

        if str(row["status"] or "") != "pending":
            await q.message.reply_text(
                f"ℹ️ این درخواست قبلاً بررسی شده است.\nوضعیت: {row['status']}",
                reply_markup=B.amenu(),
            )
            raise ApplicationHandlerStop

        partner = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone()
        if not partner:
            await q.message.reply_text("❌ حساب همکار پیدا نشد.", reply_markup=B.amenu())
            raise ApplicationHandlerStop

        now_value = B.now()
        if action == "a":
            B.db.conn.execute(
                "UPDATE topups SET status='approved',reviewed_at=?,note=? WHERE id=? AND status='pending'",
                (now_value, "approved by admin", topup_id),
            )
            if B.db.conn.execute("SELECT changes()").fetchone()[0] != 1:
                await q.message.reply_text("ℹ️ این درخواست هم‌اکنون توسط مدیر دیگری بررسی شده است.", reply_markup=B.amenu())
                raise ApplicationHandlerStop
            B.db.conn.execute(
                "UPDATE partners SET balance=balance+?,updated_at=? WHERE id=?",
                (real_amount, now_value, pid),
            )
            B.db.conn.commit()
            new_balance = int(partner["balance"] or 0) + real_amount
            result = f"✅ شارژ تأیید شد.\n💰 مبلغ: {real_amount:,} تومان\n💳 موجودی جدید: {new_balance:,} تومان"
            chat = B.db.setting(f"partner_chat_{pid}", "")
            if chat:
                try:
                    await context.bot.send_message(
                        chat_id=int(chat),
                        text=f"✅ شارژ حساب شما تأیید شد.\n💰 مبلغ: {real_amount:,} تومان\n💳 موجودی جدید: {new_balance:,} تومان",
                        reply_markup=B.partner_kb("fa"),
                    )
                except Exception:
                    log.exception("failed to notify partner after topup approval")
        else:
            B.db.conn.execute(
                "UPDATE topups SET status='rejected',reviewed_at=?,note=? WHERE id=? AND status='pending'",
                (now_value, "rejected by admin", topup_id),
            )
            B.db.conn.commit()
            result = f"❌ شارژ رد شد.\n💰 مبلغ: {real_amount:,} تومان"
            chat = B.db.setting(f"partner_chat_{pid}", "")
            if chat:
                try:
                    await context.bot.send_message(
                        chat_id=int(chat),
                        text=f"❌ درخواست شارژ حساب شما رد شد.\n💰 مبلغ: {real_amount:,} تومان",
                        reply_markup=B.partner_kb("fa"),
                    )
                except Exception:
                    log.exception("failed to notify partner after topup rejection")

        try:
            await q.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await q.message.reply_text(result, reply_markup=B.amenu())
        raise ApplicationHandlerStop

    B.media = media
    # This handler runs before the legacy broad admin callback handler, so both
    # old 4-part and current 5-part top-up callbacks are accepted reliably.
    if not getattr(B, "_final_topup_callback_installed", False):
        B._final_topup_callback_installed = True
        # The bot's existing build registers a broad (tu|pay|req|admin) handler
        # at the default group. Negative group guarantees this exact callback is
        # consumed first and cannot fall through to an incompatible parser.
        try:
            B._APP.add_handler(CallbackQueryHandler(topup_callback, pattern=r"^tu:(?:a|r):"), group=-100000)
        except Exception:
            # If the application object is not exposed, install() is called by
            # the hardening layer with the application available in the module.
            app = getattr(B, "app", None)
            if app is not None:
                app.add_handler(CallbackQueryHandler(topup_callback, pattern=r"^tu:(?:a|r):"), group=-100000)

    B._final_safety_patch_installed = True
    log.info("final safety patch installed")
