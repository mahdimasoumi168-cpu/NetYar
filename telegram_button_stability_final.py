"""Final Telegram button/communication stability layer.

Owns high-priority Reply-keyboard paths that historically had competing
handlers. Communication is persistent and admin replies stay bound to the
partner who sent the original message.
"""
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

PARTNER_CHAT_KEYS = ("partner_chat_{pid}", "partner_chat_{phone}")


def _chat_for_partner(B, pid, phone=""):
    for template in PARTNER_CHAT_KEYS:
        key = template.format(pid=pid, phone=phone)
        value = str(B.db.setting(key, "") or "").strip()
        if value.isdigit():
            return int(value)
    return None


def install(app, B):
    if getattr(B, "_button_stability_final", False):
        return True

    async def partner_text(update, context):
        msg = update.effective_message
        if not msg or not msg.text:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = msg.text.strip()

        # This Reply-keyboard button must have one owner only.
        if text == "💬 ارتباط با مدیریت":
            pid = st.get("partner_id")
            if not pid:
                await msg.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
                raise ApplicationHandlerStop
            row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
            if not row:
                st.pop("partner_id", None)
                st["partner_active"] = False
                await msg.reply_text("⛔ حساب همکار فعال نیست. لطفاً دوباره وارد شوید.", reply_markup=B.main(uid))
                raise ApplicationHandlerStop
            # The partner's own Telegram chat is always the authoritative chat id.
            B.db.set_setting(f"partner_chat_{pid}", str(uid))
            if row["phone"]:
                B.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
            st.update(mode="final_partner_chat", final_chat_admin=None, final_chat_partner_id=int(pid))
            await msg.reply_text(
                "💬 ارتباط با مدیریت فعال شد.\n\nپیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\nهمه پیام‌ها برای مدیریت ارسال می‌شوند.\n\nبرای خروج، «❌ انصراف» را بزنید."
            )
            raise ApplicationHandlerStop

        if st.get("mode") != "final_partner_chat":
            return
        pid = st.get("final_chat_partner_id") or st.get("partner_id")
        if not pid:
            return
        admins = list(getattr(B, "ADM", []) or [])
        if not admins:
            await msg.reply_text("❌ مدیریت در دسترس نیست.")
            raise ApplicationHandlerStop
        row = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=? LIMIT 1", (int(pid),)).fetchone()
        header = f"💬 پیام همکار\n👤 {row['name'] if row else '-'}\n📱 {row['phone'] if row else '-'}\n"
        sent = 0
        for aid in admins:
            try:
                sent_msg = await context.bot.send_message(chat_id=int(aid), text=header + "\n" + msg.text)
                B.db.set_setting(f"admin_reply_map_{sent_msg.message_id}", str(uid))
                sent += 1
            except Exception:
                pass
        await msg.reply_text("✅ پیام برای مدیریت ارسال شد." if sent else "❌ ارسال پیام به مدیریت انجام نشد.")
        raise ApplicationHandlerStop

    async def partner_media(update, context):
        msg = update.effective_message
        if not msg:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "final_partner_chat":
            return
        pid = st.get("final_chat_partner_id") or st.get("partner_id")
        if not pid:
            return
        admins = list(getattr(B, "ADM", []) or [])
        row = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=? LIMIT 1", (int(pid),)).fetchone()
        header = f"💬 رسانه از همکار\n👤 {row['name'] if row else '-'}\n📱 {row['phone'] if row else '-'}"
        fid = ""
        kind = ""
        if msg.photo:
            fid = msg.photo[-1].file_id; kind = "photo"
        elif msg.document:
            fid = msg.document.file_id; kind = "document"
        elif msg.video:
            fid = msg.video.file_id; kind = "video"
        elif msg.voice:
            fid = msg.voice.file_id; kind = "voice"
        elif msg.audio:
            fid = msg.audio.file_id; kind = "audio"
        if not fid:
            return
        sent = 0
        for aid in admins:
            try:
                if kind == "photo": out = await context.bot.send_photo(int(aid), fid, caption=header)
                elif kind == "document": out = await context.bot.send_document(int(aid), fid, caption=header)
                elif kind == "video": out = await context.bot.send_video(int(aid), fid, caption=header)
                elif kind == "voice": out = await context.bot.send_voice(int(aid), fid, caption=header)
                else: out = await context.bot.send_audio(int(aid), fid, caption=header)
                B.db.set_setting(f"admin_reply_map_{out.message_id}", str(uid))
                sent += 1
            except Exception:
                pass
        await msg.reply_text("✅ پیام رسانه‌ای برای مدیریت ارسال شد." if sent else "❌ ارسال رسانه به مدیریت انجام نشد.")
        raise ApplicationHandlerStop

    async def admin_reply(update, context):
        msg = update.effective_message
        if not msg or not B.admin(update.effective_user.id):
            return
        reply = msg.reply_to_message
        if not reply:
            return
        target = str(B.db.setting(f"admin_reply_map_{reply.message_id}", "") or "").strip()
        if not target or not target.isdigit():
            return
        chat = int(target)
        try:
            if msg.text:
                out = await context.bot.send_message(chat_id=chat, text="👔 پاسخ مدیریت\n\n" + msg.text)
            elif msg.photo:
                out = await context.bot.send_photo(chat_id=chat, photo=msg.photo[-1].file_id, caption="👔 پاسخ مدیریت")
            elif msg.document:
                out = await context.bot.send_document(chat_id=chat, document=msg.document.file_id, caption="👔 پاسخ مدیریت")
            elif msg.video:
                out = await context.bot.send_video(chat_id=chat, video=msg.video.file_id, caption="👔 پاسخ مدیریت")
            elif msg.voice:
                out = await context.bot.send_voice(chat_id=chat, voice=msg.voice.file_id, caption="👔 پاسخ مدیریت")
            elif msg.audio:
                out = await context.bot.send_audio(chat_id=chat, audio=msg.audio.file_id, caption="👔 پاسخ مدیریت")
            else:
                return
            B.db.set_setting(f"admin_reply_map_{out.message_id}", str(update.effective_user.id))
            await msg.reply_text("✅ پاسخ برای همکار ارسال شد.")
            raise ApplicationHandlerStop
        except Exception:
            await msg.reply_text("❌ ارسال پاسخ به همکار انجام نشد.")
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.VOICE | filters.AUDIO, partner_media), group=-10000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partner_text), group=-10000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.TEXT, admin_reply), group=-9999)
    B._button_stability_final = True
    return True
