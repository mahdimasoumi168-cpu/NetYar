"""Reliable two-way management chat for authenticated partners."""
import os, logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.management_destination_guard")

def _admins(B):
    vals = []
    for src in (getattr(B, "ADM", set()), os.getenv("ADMIN_IDS", "").replace(";", ",")):
        for x in (src if isinstance(src, (set, list, tuple)) else str(src).split(",")):
            s = str(x).strip()
            if s.lstrip("-").isdigit() and int(s) not in vals:
                vals.append(int(s))
    return vals

def _resolve(B, uid):
    st = B.S.setdefault(uid, {})
    for x in (st.get("final_chat_admin"), st.get("management_chat_id"), *_admins(B)):
        if str(x).lstrip("-").isdigit():
            admin = int(x)
            st["final_chat_admin"] = admin
            st["management_chat_id"] = admin
            return admin
    return None

def _chat_kb(side):
    if side == "admin":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ پاسخ دادن", callback_data="chat:reply")],
            [InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت", callback_data="chat:back")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ پاسخ دادن", callback_data="chat:reply")],
        [InlineKeyboardButton("⬅️ بازگشت به پنل همکاران", callback_data="chat:back")],
    ])

def _bind(B, partner_uid, admin_uid):
    pst = B.S.setdefault(int(partner_uid), {})
    ast = B.S.setdefault(int(admin_uid), {})
    pst.update(mode="final_partner_chat", final_chat_admin=int(admin_uid), final_chat_partner_id=pst.get("partner_id"), chat_reply_pending=False)
    ast.update(mode="final_admin_chat", final_chat_partner=int(partner_uid), final_chat_partner_id=pst.get("partner_id"), chat_reply_pending=False)

def install(app, B):
    if getattr(B, "_management_destination_guard", False):
        return True

    async def text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not getattr(msg, "text", None):
            return
        st = B.S.setdefault(user.id, {})
        if st.get("mode") != "final_partner_chat":
            return
        admin = _resolve(B, user.id)
        if not admin:
            await msg.reply_text("❌ مقصد مدیریت هنوز در تنظیمات ربات تعریف نشده است.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop
        _bind(B, user.id, admin)
        try:
            await context.bot.send_message(chat_id=admin, text=f"👥 پیام همکار\n\n{msg.text.strip()}", reply_markup=_chat_kb("admin"))
            await msg.reply_text("✅ پیام برای مدیریت ارسال شد.", reply_markup=_chat_kb("partner"))
        except Exception:
            log.exception("management text relay failed")
            await msg.reply_text("❌ ارسال پیام به مدیریت انجام نشد؛ لطفاً دوباره تلاش کنید.", reply_markup=_chat_kb("partner"))
        raise ApplicationHandlerStop

    async def media(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user:
            return
        st = B.S.setdefault(user.id, {})
        if st.get("mode") != "final_partner_chat":
            return
        admin = _resolve(B, user.id)
        if not admin:
            return
        _bind(B, user.id, admin)
        try:
            if msg.photo:
                await context.bot.send_photo(chat_id=admin, photo=msg.photo[-1].file_id, caption="👥 تصویر از همکار", reply_markup=_chat_kb("admin"))
            elif msg.voice:
                await context.bot.send_voice(chat_id=admin, voice=msg.voice.file_id, caption="👥 ویس از همکار", reply_markup=_chat_kb("admin"))
            elif msg.audio:
                await context.bot.send_audio(chat_id=admin, audio=msg.audio.file_id, caption="👥 صوت از همکار", reply_markup=_chat_kb("admin"))
            elif msg.document:
                await context.bot.send_document(chat_id=admin, document=msg.document.file_id, caption="👥 فایل از همکار", reply_markup=_chat_kb("admin"))
            elif msg.video:
                await context.bot.send_video(chat_id=admin, video=msg.video.file_id, caption="👥 ویدیو از همکار", reply_markup=_chat_kb("admin"))
            else:
                return
            await msg.reply_text("✅ فایل برای مدیریت ارسال شد.", reply_markup=_chat_kb("partner"))
        except Exception:
            log.exception("management media relay failed")
            await msg.reply_text("❌ ارسال فایل به مدیریت انجام نشد.", reply_markup=_chat_kb("partner"))
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-60001)
    app.add_handler(MessageHandler(filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.VIDEO, media), group=-60000)
    B._management_destination_guard = True
    return True
