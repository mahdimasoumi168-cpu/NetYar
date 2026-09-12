"""Reliable Telegram notification owner.

Replaces the legacy notification helper with a small, retrying implementation.
It deliberately keeps the same call signature and also accepts files= for
request attachments, so every service request can reach management reliably.
"""
import asyncio
import logging

log = logging.getLogger("netyar.telegram.notification_guard")


def install(app, B):
    if getattr(B, "_telegram_notification_guard", False):
        return

    async def notify_admins(application, message, request_id=None, inline=None, files=None):
        admins = list(getattr(B, "ADM", set()) or [])
        if not admins:
            log.warning("No Telegram admins configured; notification not sent")
            return False

        markup = inline
        if request_id and markup is None:
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"panel:req:{request_id}")],
                [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{request_id}"),
                 InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{request_id}")],
                [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{request_id}")],
            ])

        ok = True
        bot = application.bot
        for aid in admins:
            delivered = False
            for attempt in range(3):
                try:
                    await bot.send_message(chat_id=int(aid), text=str(message), reply_markup=markup)
                    delivered = True
                    break
                except Exception:
                    if attempt == 2:
                        log.exception("admin text notification failed: admin=%s request=%s", aid, request_id)
                    else:
                        await asyncio.sleep(0.7 * (attempt + 1))

            for item in list(files or []):
                if not item:
                    continue
                kind = str(item.get("type", "photo")) if isinstance(item, dict) else "photo"
                file_id = item.get("file_id") if isinstance(item, dict) else str(item)
                if not file_id:
                    continue
                for attempt in range(3):
                    try:
                        if kind == "document":
                            await bot.send_document(chat_id=int(aid), document=file_id)
                        else:
                            await bot.send_photo(chat_id=int(aid), photo=file_id)
                        break
                    except Exception:
                        if attempt == 2:
                            log.exception("admin attachment notification failed: admin=%s request=%s", aid, request_id)
                        else:
                            await asyncio.sleep(0.7 * (attempt + 1))
            if not delivered:
                ok = False
        return ok

    B.notify_admins = notify_admins
    B._telegram_notification_guard = True
    log.info("Telegram notification guard installed")
