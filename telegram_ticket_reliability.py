"""Reliable free-form partner/admin ticket messaging for Telegram."""
import logging
from telegram.ext import ApplicationHandlerStop, MessageHandler, filters

log = logging.getLogger("netyar.telegram.ticket_reliability")


def _button(pid):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ پیام", callback_data=f"ticket:reply:{pid}")]])


def _chat(B, pid):
    try:
        value = B.db.setting(f"partner_chat_{pid}", "")
        if not value:
            p = B.db.conn.execute("SELECT phone FROM partners WHERE id=?", (pid,)).fetchone()
            if p and p["phone"]:
                value = B.db.setting(f"partner_chat_{p['phone']}", "")
        return int(value) if value else None
    except Exception:
        return None


async def _send(bot, chat_id, message, caption, markup):
    if message.photo:
        await bot.send_photo(chat_id, message.photo[-1].file_id, caption=caption, reply_markup=markup)
    elif message.video:
        await bot.send_video(chat_id, message.video.file_id, caption=caption, reply_markup=markup)
    elif message.voice:
        await bot.send_voice(chat_id, message.voice.file_id, caption=caption, reply_markup=markup)
    elif message.audio:
        await bot.send_audio(chat_id, message.audio.file_id, caption=caption, reply_markup=markup)
    elif message.document:
        await bot.send_document(chat_id, message.document.file_id, caption=caption, reply_markup=markup)
    elif message.animation:
        await bot.send_animation(chat_id, message.animation.file_id, caption=caption, reply_markup=markup)
    else:
        text = (message.text or "").strip()
        if not text:
            return False
        await bot.send_message(chat_id, text=caption, reply_markup=markup)
    return True


async def _media_or_text(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    st = B.S.setdefault(user.id, {})
    mode = st.get("mode")
    if mode not in {"partner_message", "ticket_admin_reply", "ticket_partner_reply"}:
        return

    caption = (message.caption or message.text or "").strip()
    try:
        if mode == "partner_message":
            pid = st.get("partner_id")
            if not pid:
                return
            p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
            if not p:
                return
            # Register the partner's real Telegram chat immediately. This is
            # what lets an administrator later start a conversation from
            # «💬 ارتباط با همکار» without requiring a previous reply button.
            B.db.set_setting(f"partner_chat_{pid}", str(user.id))
            if p["phone"]:
                B.db.set_setting(f"partner_chat_{p['phone']}", str(user.id))
            text = f"📨 پیام همکار\n👤 {p['name']}\n📱 {p['phone']}\n🆔 شناسه همکار: {pid}\n\n{caption or 'پیام بدون متن'}"
            B.db.set_setting(f"ticket_admin_{pid}", str(next(iter(B.ADM), "")))
            for aid in B.ADM:
                await _send(context.bot, int(aid), message, text, _button(pid))
            await message.reply_text("✅ پیام شما برای مدیریت ارسال شد.\nهر تعداد پیام، متن، عکس، ویدیو یا ویس خواستید می‌توانید ارسال کنید.")
            raise ApplicationHandlerStop

        if mode == "ticket_admin_reply" and B.admin(user.id):
            pid = st.get("ticket_partner_id")
            chat_id = _chat(B, pid)
            if not chat_id:
                await message.reply_text("❌ ارتباط با همکار پیدا نشد. همکار باید یک‌بار وارد پنل شود.")
                raise ApplicationHandlerStop
            text = f"👔 پیام مدیریت\n\n{caption or 'پیام بدون متن'}"
            await _send(context.bot, chat_id, message, text, _button(pid))
            B.db.set_setting(f"ticket_admin_{pid}", str(user.id))
            await message.reply_text("✅ پیام برای همکار ارسال شد.\nمی‌توانید پیام بعدی را هم بفرستید.")
            raise ApplicationHandlerStop

        if mode == "ticket_partner_reply":
            pid = st.get("partner_id")
            admin_id = B.db.setting(f"ticket_admin_{pid}", "").strip() or str(next(iter(B.ADM), ""))
            if not admin_id:
                await message.reply_text("❌ مدیریت برای پاسخ در دسترس نیست.")
                raise ApplicationHandlerStop
            p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
            text = f"📨 پیام همکار\n👤 {p['name'] if p else '-'}\n📱 {p['phone'] if p else '-'}\n\n{caption or 'پیام بدون متن'}"
            await _send(context.bot, int(admin_id), message, text, _button(pid))
            await message.reply_text("✅ پیام شما برای مدیریت ارسال شد.\nمی‌توانید پیام بعدی را هم بفرستید.")
            raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("ticket free-form forwarding failed")
        try:
            await message.reply_text("❌ ارسال پیام انجام نشد. لطفاً دوباره تلاش کنید.")
        except Exception:
            pass
        raise ApplicationHandlerStop


def install(app, B):
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            lambda u, c: _media_or_text(u, c, B),
        ),
        group=-92,
    )
