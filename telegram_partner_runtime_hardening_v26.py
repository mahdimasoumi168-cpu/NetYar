"""Final partner runtime hardening.

Management chat is a real waiting mode: the button only changes state; the
first actual partner message/media is consumed here before legacy handlers can
turn it into a generic ui2 execution error. Night-shift authenticated partners
also keep their session while entering service data; the closed-hours gate must
not reject a valid partner merely because the current service changed mode.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.partner_runtime_hardening_v26")
MANAGEMENT = "💬 ارتباط با مدیریت"
CANCEL = "❌ انصراف"


def _admin_ids(B):
    out = []
    for src in (getattr(B, "ADM", ()), getattr(B, "ADMINS", ())):
        for value in src or ():
            try:
                n = int(value)
                if n not in out:
                    out.append(n)
            except Exception:
                pass
    return out


def _partner_kb(B, uid):
    try:
        return B.partner_kb_for(uid, "fa")
    except Exception:
        try:
            import telegram_ui_policy_v2 as UI
            return UI.inline([
                ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
                ["📱 حل مشکل سیم کارت ایرانسل", "🪪 فیدای غیر حضوری"],
                ["📱 خدمات سیم کارت", "🔎 پیگیری کد"],
                ["📋 سوابق", "💰 موجودی"],
                ["🎫 تیکت به مدیریت", MANAGEMENT],
                ["🚪 خروج از پنل"],
                [CANCEL],
            ], B, uid)
        except Exception:
            return None


def _chat_kb(B, uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(CANCEL, callback_data="partner_chat_cancel")]])


def _resolve_admin(B, uid):
    st = B.S.setdefault(uid, {})
    for value in (st.get("final_chat_admin"), st.get("management_chat_id"), *_admin_ids(B)):
        try:
            n = int(value)
            st["final_chat_admin"] = n
            st["management_chat_id"] = n
            return n
        except Exception:
            pass
    return None


def _active_partner(B, uid):
    st = B.S.setdefault(uid, {})
    if st.get("partner_logged_out") or not st.get("partner_active") or not st.get("partner_id"):
        return False
    try:
        row = B.db.conn.execute(
            "SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(st["partner_id"]),)
        ).fetchone()
        return bool(row)
    except Exception:
        return False


def install(app, B):
    if getattr(B, "_partner_runtime_hardening_v26", False):
        return

    async def cancel_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or str(q.data or "") != "partner_chat_cancel":
            return
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "final_partner_chat":
            return
        await q.answer()
        st["mode"] = "partner"
        st["chat_reply_pending"] = False
        await q.message.reply_text("↩️ ارتباط با مدیریت پایان یافت.", reply_markup=_partner_kb(B, uid))
        raise ApplicationHandlerStop

    async def content(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "final_partner_chat":
            return
        if not _active_partner(B, uid):
            st["mode"] = None
            await msg.reply_text("⛔ نشست همکار معتبر نیست. لطفاً دوباره وارد پنل همکاران شوید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

        if getattr(msg, "text", None) and msg.text.strip() == CANCEL:
            st["mode"] = "partner"
            st["chat_reply_pending"] = False
            await msg.reply_text("↩️ ارتباط با مدیریت پایان یافت.", reply_markup=_partner_kb(B, uid))
            raise ApplicationHandlerStop

        admin = _resolve_admin(B, uid)
        if not admin:
            await msg.reply_text("⚠️ مقصد مدیریت تنظیم نشده است. پنل همکاران شما باز ماند؛ بعداً دوباره تلاش کنید.", reply_markup=_partner_kb(B, uid))
            raise ApplicationHandlerStop

        try:
            if getattr(msg, "photo", None):
                await context.bot.send_photo(chat_id=admin, photo=msg.photo[-1].file_id, caption="👥 پیام تصویری از همکار")
            elif getattr(msg, "document", None):
                await context.bot.send_document(chat_id=admin, document=msg.document.file_id, caption="👥 فایل از همکار")
            elif getattr(msg, "voice", None):
                await context.bot.send_voice(chat_id=admin, voice=msg.voice.file_id, caption="👥 ویس از همکار")
            elif getattr(msg, "video", None):
                await context.bot.send_video(chat_id=admin, video=msg.video.file_id, caption="👥 ویدیو از همکار")
            elif getattr(msg, "audio", None):
                await context.bot.send_audio(chat_id=admin, audio=msg.audio.file_id, caption="👥 صوت از همکار")
            elif getattr(msg, "text", None):
                await context.bot.send_message(chat_id=admin, text=f"👥 پیام همکار\n\n{msg.text.strip()}")
            else:
                await msg.reply_text("⚠️ این نوع پیام قابل ارسال نیست. متن، عکس، فایل، ویس یا ویدیو بفرستید.", reply_markup=_chat_kb(B, uid))
                raise ApplicationHandlerStop
            await msg.reply_text("✅ پیام شما برای مدیریت ارسال شد.", reply_markup=_chat_kb(B, uid))
        except Exception:
            log.exception("management content relay failed")
            await msg.reply_text("❌ ارسال به مدیریت انجام نشد؛ پنل شما باز است. دوباره تلاش کنید.", reply_markup=_chat_kb(B, uid))
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^partner_chat_cancel$"), group=-100000)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, content), group=-99999)
    B._partner_runtime_hardening_v26 = True
    log.info("Partner runtime hardening v26 installed")
