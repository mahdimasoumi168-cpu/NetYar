"""Production hotfix v3: deterministic fixes after legacy compatibility layers."""
import logging
import os

log = logging.getLogger("netyar.production_hotfix_v3")


def install():
    import bot as B
    if getattr(B, "_production_hotfix_v3", False):
        return

    # Accept the variable name documented by README/Railway as well as the
    # legacy BOT_TOKEN name used by bot.py.
    if not os.getenv("BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        os.environ["BOT_TOKEN"] = os.environ["TELEGRAM_BOT_TOKEN"].strip()

    # Forward submitted photos/documents to admins. The old notification only
    # contained text, so admins could not see the customer's evidence.
    old_notify = B.notify_admins
    async def notify_admins_with_files(app, message, request_id=None, inline=None):
        await old_notify(app, message, request_id=request_id, inline=inline)
        if not request_id or not B.ADM:
            return
        try:
            rows = B.db.conn.execute(
                "SELECT field_key,file_id FROM request_answers WHERE request_id=? AND file_id<>'' ORDER BY id",
                (request_id,),
            ).fetchall()
            for row in rows:
                fid = str(row["file_id"] or "").strip()
                if not fid:
                    continue
                caption = f"📎 فایل درخواست {request_id} | {row['field_key']}"
                for aid in B.ADM:
                    try:
                        await app.bot.send_document(chat_id=int(aid), document=fid, caption=caption)
                    except Exception:
                        try:
                            await app.bot.send_photo(chat_id=int(aid), photo=fid, caption=caption)
                        except Exception:
                            log.exception("Could not forward request attachment")
        except Exception:
            log.exception("request attachment notification failed")
    B.notify_admins = notify_admins_with_files

    # Add approve/reject actions to request management while preserving all
    # existing top-up/reply callbacks.
    old_admin_cb = B.admin_cb
    async def admin_cb_with_decision(update, context):
        q = update.callback_query
        data = str(q.data or "")
        if data.startswith("req:a:") or data.startswith("req:x:"):
            await q.answer()
            if not B.admin(q.from_user.id):
                return
            try:
                rid = int(data.split(":", 2)[2])
                new_status = "approved" if data.startswith("req:a:") else "rejected"
                r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                if not r:
                    return await q.message.reply_text("❌ درخواست پیدا نشد.", reply_markup=B.amenu())
                if r["status"] in {"approved", "rejected", "completed"}:
                    return await q.message.reply_text(f"ℹ️ این درخواست قبلاً بررسی شده است: {r['status']}", reply_markup=B.amenu())
                B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (new_status, B.now(), rid))
                B.db.audit("telegram", q.from_user.id, new_status, f"request:{rid}", r["tracking_code"])
                B.db.conn.commit()

                # Direct Telegram customer.
                user = B.db.conn.execute(
                    "SELECT external_id FROM users WHERE id=? AND platform='telegram'", (r["user_id"],)
                ).fetchone()
                if user:
                    try:
                        await q.bot.send_message(
                            chat_id=int(user["external_id"]),
                            text=f"{'✅' if new_status == 'approved' else '❌'} وضعیت درخواست شما تغییر کرد.\n🎫 کد پیگیری: {r['tracking_code']}\n📌 وضعیت: {new_status}",
                        )
                    except Exception:
                        log.exception("customer status notification failed")
                else:
                    # Partner requests use partners.id in the legacy user_id
                    # column; partner_chat_* stores the active Telegram chat.
                    chat = B.db.setting(f"partner_chat_{r['user_id']}", "")
                    if chat:
                        try:
                            await q.bot.send_message(
                                chat_id=int(chat),
                                text=f"{'✅' if new_status == 'approved' else '❌'} وضعیت درخواست خدمات شما تغییر کرد.\n🎫 کد پیگیری: {r['tracking_code']}\n📌 وضعیت: {new_status}",
                                reply_markup=B.partner_kb("fa"),
                            )
                        except Exception:
                            log.exception("partner status notification failed")
                await q.message.edit_reply_markup(reply_markup=None)
                return await q.message.reply_text(
                    f"{'✅ درخواست تأیید شد.' if new_status == 'approved' else '❌ درخواست رد شد.'}\n🎫 {r['tracking_code']}",
                    reply_markup=B.amenu(),
                )
            except Exception:
                log.exception("request decision callback failed")
                return await q.message.reply_text("❌ خطا در بررسی درخواست.", reply_markup=B.amenu())

        if data.startswith("req:v:"):
            await q.answer()
            if not B.admin(q.from_user.id):
                return
            try:
                rid = int(data.split(":", 2)[2])
                r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                if not r:
                    return await q.message.reply_text("❌ درخواست پیدا نشد.", reply_markup=B.amenu())
                answers = B.db.conn.execute(
                    "SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)
                ).fetchall()
                lines = [
                    f"🎫 {r['tracking_code']}",
                    f"🧾 خدمت: {r['service_key']}",
                    f"📌 وضعیت: {r['status']}",
                    f"💰 مبلغ: {r['amount']:,} تومان",
                    f"💳 پرداخت: {r['payment_status']}",
                ]
                for a in answers:
                    if a["answer"]:
                        lines.append(f"• {a['field_key']}: {a['answer']}")
                    elif a["file_id"]:
                        lines.append(f"• {a['field_key']}: 📎 فایل پیوست")
                buttons = [
                    [B.InlineKeyboardButton("✅ تأیید درخواست", callback_data=f"req:a:{rid}"), B.InlineKeyboardButton("❌ رد درخواست", callback_data=f"req:x:{rid}")],
                    [B.InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")],
                ]
                return await q.message.reply_text("\n".join(lines)[:3900], reply_markup=B.InlineKeyboardMarkup(buttons))
            except Exception:
                log.exception("request view callback failed")
                return await q.message.reply_text("❌ خطا در نمایش درخواست.", reply_markup=B.amenu())

        return await old_admin_cb(update, context)
    B.admin_cb = admin_cb_with_decision

    B._production_hotfix_v3 = True
    log.info("production hotfix v3 installed")
