"""Media support for the Telegram partner/admin ticket conversation."""
import logging
from telegram.ext import MessageHandler, filters

log = logging.getLogger("netyar.telegram.ticket_media")


def _ticket_button(partner_id):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ پاسخ پیام", callback_data=f"ticket:reply:{partner_id}")]
    ])


def _partner_chat(B, pid):
    try:
        value = B.db.setting(f"partner_chat_{pid}", "")
        return int(value) if value else None
    except Exception:
        return None


async def _send_media(bot, chat_id, message, caption, markup):
    if message.photo:
        await bot.send_photo(chat_id=chat_id, photo=message.photo[-1].file_id,
                             caption=caption, reply_markup=markup)
    elif message.video:
        await bot.send_video(chat_id=chat_id, video=message.video.file_id,
                             caption=caption, reply_markup=markup)
    elif message.voice:
        await bot.send_voice(chat_id=chat_id, voice=message.voice.file_id,
                             caption=caption, reply_markup=markup)
    elif message.document:
        await bot.send_document(chat_id=chat_id, document=message.document.file_id,
                                caption=caption, reply_markup=markup)
    elif message.audio:
        await bot.send_audio(chat_id=chat_id, audio=message.audio.file_id,
                             caption=caption, reply_markup=markup)
    else:
        return False
    return True


async def _media(update, context, B):
    message = update.effective_message
    if not message:
        return
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    if mode not in {"partner_message", "ticket_admin_reply", "ticket_partner_reply"}:
        return

    caption = (message.caption or "").strip()
    markup = None

    try:
        if mode == "partner_message":
            pid = st.get("partner_id")
            if not pid:
                return
            p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
            if not p:
                return
            text = (
                f"📨 پیام جدید همکار\n👤 {p['name']}\n📱 {p['phone']}\n"
                f"🆔 شناسه همکار: {pid}\n\n{caption or 'پیام رسانه‌ای'}"
            )
            markup = _ticket_button(pid)
            for aid in B.ADM:
                await _send_media(context.bot, int(aid), message, text, markup)
            return await message.reply_text("✅ پیام شما برای مدیریت ارسال شد.\nمی‌توانید پیام دیگری هم بفرستید.")

        if mode == "ticket_admin_reply" and B.admin(uid):
            pid = st.get("ticket_partner_id")
            chat_id = _partner_chat(B, pid)
            if not chat_id:
                return await message.reply_text("❌ ارتباط با همکار پیدا نشد.")
            text = f"👔 پیام مدیریت\n\n{caption or 'پیام رسانه‌ای'}"
            await _send_media(context.bot, chat_id, message, text, _ticket_button(pid))
            B.db.set_setting(f"ticket_admin_{pid}", str(uid))
            return await message.reply_text("✅ پیام برای همکار ارسال شد.\nمی‌توانید پیام دیگری هم بفرستید.")

        if mode == "ticket_partner_reply" and st.get("partner_id"):
            pid = st.get("partner_id")
            admin_id = B.db.setting(f"ticket_admin_{pid}", "").strip() or str(next(iter(B.ADM), ""))
            if not admin_id:
                return await message.reply_text("❌ مدیریت برای پاسخ در دسترس نیست.")
            p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
            text = (
                f"📨 پیام همکار\n👤 {p['name'] if p else '-'}\n"
                f"📱 {p['phone'] if p else '-'}\n\n{caption or 'پیام رسانه‌ای'}"
            )
            await _send_media(context.bot, int(admin_id), message, text, _ticket_button(pid))
            return await message.reply_text("✅ پیام شما برای مدیریت ارسال شد.\nمی‌توانید پیام دیگری هم بفرستید.")
    except Exception:
        log.exception("ticket media forwarding failed")
        try:
            await message.reply_text("❌ ارسال پیام رسانه‌ای انجام نشد. دوباره تلاش کنید.")
        except Exception:
            pass


def install(app, B):
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.VOICE | filters.Document.ALL | filters.AUDIO,
            lambda u, c: _media(u, c, B),
        ),
        group=-3,
    )
