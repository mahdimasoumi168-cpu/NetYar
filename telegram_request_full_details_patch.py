"""Final request details/controls and admin notification enhancement.

Keeps the existing business handlers intact while ensuring every admin request
contains all collected fields and uploaded media, and uses one canonical
request keyboard.  The captcha flow remains manual: an admin can send an image
for the partner/user to inspect and enter the returned code manually.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.request_full_details")


def _keyboard(rid):
    # Transfer-to-bottom is intentionally the first/largest navigation action.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
        [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}"),
         InlineKeyboardButton("🔐 درخواست کد", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("🧩 درخواست کپچا", callback_data=f"req:captcha:{rid}"),
         InlineKeyboardButton("📝 درخواست نوشتار چکاپ", callback_data=f"req:checkup:{rid}")],
        [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}")],
        [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}"),
         InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
        [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}")],
    ])


def _value(v):
    if v is None:
        return ""
    return str(v).strip()


def _full_text(B, rid):
    r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (int(rid),)).fetchone()
    if not r:
        return None, []
    rows = B.db.conn.execute(
        "SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",
        (int(rid),),
    ).fetchall()
    lines = [
        "📋 درخواست جدید / اطلاعات کامل",
        f"🆔 شناسه درخواست: {_value(r['id'])}",
        f"🎫 کد پیگیری: {_value(r['tracking_code'])}",
        f"🧾 خدمت: {_value(r['service_key'])}",
        f"📌 وضعیت: {_value(r['status'])}",
    ]
    # Include every populated request-table field except internal columns.
    try:
        for key in r.keys():
            if key in {"id", "tracking_code", "service_key", "status", "created_at", "updated_at"}:
                continue
            val = _value(r[key])
            if val and key not in {"user_id"}:
                lines.append(f"• {key}: {val}")
    except Exception:
        pass
    lines.append("")
    lines.append("📥 اطلاعات واردشده توسط کاربر:")
    file_ids = []
    for row in rows:
        key = _value(row["field_key"]) or "اطلاعات"
        ans = _value(row["answer"])
        fid = _value(row["file_id"])
        if ans:
            lines.append(f"• {key}: {ans}")
        elif fid:
            lines.append(f"• {key}: 📎 تصویر/فایل پیوست شد")
            file_ids.append((key, fid))
    return "\n".join(lines), file_ids


def install(app, B):
    if getattr(B, "_request_full_details_patch", False):
        return True

    async def callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = str(q.data or "")
        if data == "" or not data.startswith("req:"):
            return
        parts = data.split(":")
        if len(parts) != 3:
            return
        action = parts[1]
        try:
            rid = int(parts[2])
        except Exception:
            return

        if action == "v":
            text, files = _full_text(B, rid)
            if text is None:
                await q.answer("درخواست پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop
            await q.message.reply_text(text, reply_markup=_keyboard(rid))
            for key, fid in files:
                try:
                    await context.bot.send_photo(chat_id=q.from_user.id, photo=fid, caption=f"📎 {key}")
                except Exception:
                    try:
                        await context.bot.send_document(chat_id=q.from_user.id, document=fid, caption=f"📎 {key}")
                    except Exception:
                        log.exception("request media delivery failed: %s", rid)
            await q.answer("اطلاعات کامل نمایش داده شد")
            raise ApplicationHandlerStop

        if action == "bottom":
            text, files = _full_text(B, rid)
            if text is None:
                await q.answer("درخواست پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop
            await q.message.reply_text(text, reply_markup=_keyboard(rid))
            for key, fid in files:
                try:
                    await context.bot.send_photo(chat_id=q.from_user.id, photo=fid, caption=f"📎 {key}")
                except Exception:
                    try:
                        await context.bot.send_document(chat_id=q.from_user.id, document=fid, caption=f"📎 {key}")
                    except Exception:
                        log.exception("request bottom media delivery failed: %s", rid)
            await q.answer("درخواست به آخر چت منتقل شد")
            raise ApplicationHandlerStop

        # Other request actions remain owned by the established request router.
        return

    # This handler is installed before the legacy request overlay by entrypoint.
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^req:(v|bottom):\d+$"), group=0)
    B._request_full_details_patch = True
    return True


def finalize(B):
    """Wrap the final admin notifier so every request notification is complete."""
    if getattr(B, "_request_full_notify_patch", False):
        return True
    old = getattr(B, "notify_admins", None)
    if old is None:
        return False

    async def notify_admins(application, message, request_id=None, inline=None, files=None, **kwargs):
        result = await old(application, message, request_id, inline, files, **kwargs)
        if not request_id:
            return result
        try:
            text, stored_files = _full_text(B, int(request_id))
            if text:
                admins = list(dict.fromkeys(getattr(B, "ADM", set()) or []))
                # Avoid duplicate full-detail messages where the original notifier
                # already delivered the same request text; this enhancement is the
                # authoritative complete copy with canonical controls.
                mk = _keyboard(int(request_id))
                for aid in admins:
                    try:
                        await application.bot.send_message(chat_id=int(aid), text=text, reply_markup=mk)
                    except Exception:
                        log.exception("complete request notification failed: %s", request_id)
                    for key, fid in stored_files:
                        try:
                            await application.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"📎 {key} | درخواست #{request_id}")
                        except Exception:
                            try:
                                await application.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 {key} | درخواست #{request_id}")
                            except Exception:
                                log.exception("request attachment notification failed: %s", request_id)
        except Exception:
            log.exception("complete request notification wrapper failed: %s", request_id)
        return result

    B.notify_admins = notify_admins
    B._request_full_notify_patch = True
    return True
