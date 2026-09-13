"""High-priority partner communication resolver.

Resolves every active Telegram partner through the canonical link table first,
then legacy settings. Also owns the highest-priority text/media relay so that
legacy handlers cannot consume the first message after admin selects a partner.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters


def install(app, B):
    if getattr(B, "_partner_chat_reliability", False):
        return True

    def resolve(pid, phone=None):
        try:
            row = B.db.conn.execute(
                "SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=? LIMIT 1",
                (int(pid),),
            ).fetchone()
            value = str(row["telegram_user_id"] or "").strip() if row else ""
            if value.isdigit():
                chat = int(value)
                B.db.set_setting(f"partner_chat_{pid}", str(chat))
                if phone:
                    B.db.set_setting(f"partner_chat_{phone}", str(chat))
                return chat
        except Exception:
            pass
        for key in (f"partner_chat_{pid}", f"partner_chat_{phone}" if phone else ""):
            if not key:
                continue
            value = str(B.db.setting(key, "") or "").strip()
            if value.isdigit():
                return int(value)
        return None

    def buttons(rid):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
            [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
            [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}")],
            [InlineKeyboardButton("🧩 درخواست کپچا", callback_data=f"req:captcha:{rid}"), InlineKeyboardButton("📝 درخواست نوشتار چکاپ", callback_data=f"req:checkup:{rid}")],
            [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
            [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")],
        ])

    async def cb(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = str(q.data or "")
        if not (data.startswith("final:chat:") or data.startswith("req:chat:")):
            return
        try:
            pid = int(data.rsplit(":", 1)[1]) if data.startswith("final:chat:") else None
            rid = int(data.rsplit(":", 1)[1]) if data.startswith("req:chat:") else None
        except Exception:
            await q.answer("درخواست نامعتبر است", show_alert=True)
            raise ApplicationHandlerStop

        r = None
        if rid is not None:
            r = B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1", (rid,)).fetchone()
            if not r:
                await q.answer("درخواست پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop
            try:
                mapped = B.db.setting(f"request_partner_{rid}", "")
                pid = int(mapped) if str(mapped).isdigit() else None
            except Exception:
                pid = None
            if pid is None:
                try:
                    p0 = B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (r["user_id"],)).fetchone()
                    if p0:
                        pid = int(p0["id"])
                except Exception:
                    pass
            if pid is None:
                await q.answer("همکار این درخواست مشخص نیست", show_alert=True)
                raise ApplicationHandlerStop

        p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
        if not p:
            await q.answer("همکار فعال پیدا نشد", show_alert=True)
            raise ApplicationHandlerStop
        chat = resolve(pid, p["phone"])
        if not chat:
            await q.answer("چت تلگرام همکار ثبت نشده؛ همکار یک‌بار وارد پنل شود.", show_alert=True)
            raise ApplicationHandlerStop

        B.db.set_setting(f"partner_chat_{pid}", str(chat))
        if p["phone"]:
            B.db.set_setting(f"partner_chat_{p['phone']}", str(chat))
        if rid is not None:
            B.db.set_setting(f"request_partner_{rid}", str(pid))

        admin_id = int(q.from_user.id)
        ast = B.S.setdefault(admin_id, {})
        ast.update(mode="final_admin_chat", final_chat_partner=chat, final_chat_partner_id=pid)
        if rid is not None:
            ast["final_chat_rid"] = rid
        pst = B.S.setdefault(chat, {})
        pst.update(mode="final_partner_chat", partner_id=pid, final_chat_admin=admin_id)
        if rid is not None:
            pst["final_chat_rid"] = rid

        await q.answer("ارتباط فعال شد")
        title = f"👤 {p['name'] or p['phone'] or pid}"
        extra = f"\n🎫 درخواست: {r['tracking_code']}" if r is not None else ""
        await q.message.reply_text(
            f"💬 ارتباط با همکار فعال شد.\n{title}{extra}\n\nپیام، عکس، فایل، صوت یا ویس را ارسال کنید.",
            reply_markup=B.amenu(),
        )
        await context.bot.send_message(
            chat_id=chat,
            text=f"💬 مدیریت ارتباط با شما را آغاز کرد.{extra}\nهر پیام، عکس، فایل، صوت یا ویس شما برای مدیریت ارسال می‌شود.",
            reply_markup=B.partner_kb(),
        )
        if rid is not None:
            try:
                await q.message.reply_text("📌 کنترل‌های درخواست:", reply_markup=buttons(rid))
            except Exception:
                pass
        raise ApplicationHandlerStop

    async def relay_text(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or not msg.text:
            return
        uid = int(user.id)
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if mode == "final_admin_chat":
            chat = st.get("final_chat_partner")
            if not chat:
                await msg.reply_text("❌ همکار مقصد مشخص نیست.", reply_markup=B.amenu())
                raise ApplicationHandlerStop
            try:
                await context.bot.send_message(chat_id=int(chat), text=f"👔 مدیریت:\n{msg.text.strip()}")
                await msg.reply_text("✅ پیام برای همکار ارسال شد.", reply_markup=B.amenu())
            except Exception:
                await msg.reply_text("❌ ارسال پیام به همکار انجام نشد. ارتباط دوباره برقرار نشد.", reply_markup=B.amenu())
            raise ApplicationHandlerStop
        if mode == "final_partner_chat":
            admin = st.get("final_chat_admin")
            if not admin:
                await msg.reply_text("❌ مدیریت مقصد مشخص نیست.", reply_markup=B.partner_kb())
                raise ApplicationHandlerStop
            try:
                await context.bot.send_message(chat_id=int(admin), text=f"👥 همکار:\n{msg.text.strip()}")
                await msg.reply_text("✅ پیام برای مدیریت ارسال شد.", reply_markup=B.partner_kb())
            except Exception:
                await msg.reply_text("❌ ارسال پیام به مدیریت انجام نشد.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop

    async def relay_media(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user:
            return
        st = B.S.setdefault(int(user.id), {})
        mode = st.get("mode")
        try:
            if mode == "final_admin_chat":
                chat = int(st.get("final_chat_partner"))
                if msg.photo:
                    await context.bot.send_photo(chat_id=chat, photo=msg.photo[-1].file_id, caption="👔 تصویر از مدیریت")
                elif msg.voice:
                    await context.bot.send_voice(chat_id=chat, voice=msg.voice.file_id, caption="👔 ویس از مدیریت")
                elif msg.audio:
                    await context.bot.send_audio(chat_id=chat, audio=msg.audio.file_id, caption="👔 صوت از مدیریت")
                elif msg.document:
                    await context.bot.send_document(chat_id=chat, document=msg.document.file_id, caption="👔 فایل از مدیریت")
                else:
                    return
                await msg.reply_text("✅ فایل برای همکار ارسال شد.", reply_markup=B.amenu())
                raise ApplicationHandlerStop
            if mode == "final_partner_chat":
                admin = int(st.get("final_chat_admin"))
                if msg.photo:
                    await context.bot.send_photo(chat_id=admin, photo=msg.photo[-1].file_id, caption="👥 تصویر از همکار")
                elif msg.voice:
                    await context.bot.send_voice(chat_id=admin, voice=msg.voice.file_id, caption="👥 ویس از همکار")
                elif msg.audio:
                    await context.bot.send_audio(chat_id=admin, audio=msg.audio.file_id, caption="👥 صوت از همکار")
                elif msg.document:
                    await context.bot.send_document(chat_id=admin, document=msg.document.file_id, caption="👥 فایل از همکار")
                else:
                    return
                await msg.reply_text("✅ فایل برای مدیریت ارسال شد.", reply_markup=B.partner_kb())
                raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            if mode == "final_admin_chat":
                await msg.reply_text("❌ ارسال فایل به همکار انجام نشد.", reply_markup=B.amenu())
            elif mode == "final_partner_chat":
                await msg.reply_text("❌ ارسال فایل به مدیریت انجام نشد.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^(final:chat:|req:chat:)"), group=-60000)
    # These must be above legacy text/media routers; otherwise the first message
    # after selecting a partner can be consumed by an unrelated service flow.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_text), group=-59999)
    app.add_handler(MessageHandler(filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL, relay_media), group=-59998)
    B._partner_chat_reliability = True
    return True
