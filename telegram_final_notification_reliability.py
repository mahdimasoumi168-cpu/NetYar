"""Final Telegram notification reliability layer.

Installed last so legacy notification wrappers cannot silently replace the
canonical notification path. Every admin is attempted independently, request
attachments are collected automatically, and request controls use the current
req:* callbacks.
"""
import asyncio
import logging

log = logging.getLogger("netyar.telegram.final_notification_reliability")


def install(app, B):
    if getattr(B, "_final_notification_reliability", False):
        return True

    async def _send_with_retry(bot, method, chat_id, **kwargs):
        for attempt in range(3):
            try:
                await method(chat_id=chat_id, **kwargs)
                return True
            except Exception:
                if attempt == 2:
                    log.exception("notification delivery failed chat=%s", chat_id)
                else:
                    await asyncio.sleep(0.7 * (attempt + 1))
        return False

    async def notify_admins(application, message, request_id=None, inline=None, files=None):
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        admins = list(dict.fromkeys(getattr(B, "ADM", set()) or []))
        if not admins:
            log.warning("No Telegram admins configured")
            return False

        markup = inline
        if request_id and markup is None:
            rid = int(request_id)
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
                [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
                [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}")],
                [InlineKeyboardButton("🧩 درخواست کپچا", callback_data=f"req:captcha:{rid}"), InlineKeyboardButton("📝 درخواست نوشتار چکاپ", callback_data=f"req:checkup:{rid}")],
                [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
                [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")],
            ])

        attachment_items = list(files or [])
        if request_id:
            try:
                rows = B.db.conn.execute(
                    "SELECT field_key,file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",
                    (int(request_id),),
                ).fetchall()
                known = {(str(x.get("file_id")) if isinstance(x, dict) else str(x)) for x in attachment_items if x}
                for row in rows:
                    fid = str(row["file_id"] or "").strip()
                    if fid and fid not in known:
                        attachment_items.append({"type": "photo", "file_id": fid, "field_key": row["field_key"]})
                        known.add(fid)
            except Exception:
                log.exception("request attachment lookup failed: request=%s", request_id)

        tracking = str(request_id or "")
        if request_id:
            try:
                row = B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?", (int(request_id),)).fetchone()
                if row and row["tracking_code"]:
                    tracking = str(row["tracking_code"])
            except Exception:
                pass

        all_ok = True
        bot = application.bot
        for aid in admins:
            try:
                admin_id = int(aid)
            except Exception:
                all_ok = False
                continue

            sent = await _send_with_retry(bot, bot.send_message, admin_id, text=str(message), reply_markup=markup)
            if not sent:
                all_ok = False

            for item in attachment_items:
                if not item:
                    continue
                if isinstance(item, dict):
                    fid = str(item.get("file_id") or "").strip()
                    kind = str(item.get("type") or "photo").lower()
                    field = str(item.get("field_key") or "فایل درخواست")
                else:
                    fid = str(item).strip()
                    kind = "photo"
                    field = "فایل درخواست"
                if not fid:
                    continue
                caption = f"📎 {field} | درخواست {tracking}"
                if kind == "document":
                    sent_file = await _send_with_retry(bot, bot.send_document, admin_id, document=fid, caption=caption)
                else:
                    sent_file = await _send_with_retry(bot, bot.send_photo, admin_id, photo=fid, caption=caption)
                if not sent_file:
                    all_ok = False

        return all_ok

    B.notify_admins = notify_admins
    B._final_notification_reliability = True
    log.info("Final Telegram notification reliability installed")
    return True
