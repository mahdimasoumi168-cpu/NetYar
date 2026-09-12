"""Service notifications and partner-code intake for Telegram."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.notifications")
B = None


def _admin_markup(rid):
    """Manager actions shown directly under every new service notification."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"),
         InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"),
         InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])


def _partner_keyboard():
    """Partner menu: no manual 'send code to manager' option.

    The partner only receives a code request from management when the manager
    presses '📨 درخواست کد از همکار' on a service notification.
    """
    return B.kb([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        ["🎫 درخواست‌های من", "🔎 پیگیری کد"],
        ["📋 سوابق", "💰 موجودی"],
        ["📨 ارسال پیام به مدیریت"],
        ["🚪 خروج از پنل"],
        [B.CANCEL],
    ])


async def _send_to_admins(bot, text, photo_id=None, document_id=None, rid=None):
    if not B.ADM:
        return
    markup = _admin_markup(rid) if rid else None
    for aid in B.ADM:
        try:
            if photo_id:
                await bot.send_photo(chat_id=int(aid), photo=photo_id, caption=text, reply_markup=markup)
            elif document_id:
                await bot.send_document(chat_id=int(aid), document=document_id, caption=text, reply_markup=markup)
            else:
                await bot.send_message(chat_id=int(aid), text=text, reply_markup=markup)
        except Exception:
            log.exception("admin notification failed")


async def _media(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    if mode not in {"gov_photo", "fida_doc", "print"}:
        return

    # Snapshot fields before bot.media clears the workflow state.
    snapshot = dict(st)
    owner = st.get("partner_id") or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
    before = B.db.conn.execute("SELECT id FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1", (owner,)).fetchone()

    # bot.media remains the single source of truth for persisting the service.
    await B.media(update, context)

    after = B.db.conn.execute("SELECT id,tracking_code,service_key,status FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1", (owner,)).fetchone()
    photo_id = update.message.photo[-1].file_id if update.message.photo else None
    document_id = update.message.document.file_id if update.message.document else None
    title = "👔 مدیر — اعلان خدمات جدید"

    if mode == "gov_photo" and after and (not before or after["id"] != before["id"]):
        text = (
            f"{title}\n\n🆕 درخواست حل مشکل سامانه دولت من\n"
            f"🎫 کد پیگیری: {after['tracking_code']}\n👤 شناسه کاربر: {uid}\n"
            f"🪪 نوع مدرک: {snapshot.get('gov_doc_type', '-')}\n📱 موبایل مشترک: {snapshot.get('phone', '-')}\n"
            f"🎂 تاریخ تولد: {snapshot.get('dob', '-')}\n🆔 شناسه یکتا: {snapshot.get('unique_id', '-')}\n"
            f"🔖 شناسه اختصاصی: {snapshot.get('special_id', '-')}\n🛂 پاسپورت: {snapshot.get('passport', '-')}\n\n"
            "📎 مدرک مشترک در همین اعلان ارسال شده است."
        )
        await _send_to_admins(context.bot, text, photo_id, document_id, after["id"])
    elif mode == "fida_doc":
        await _send_to_admins(context.bot, f"{title}\n\n📄 مدرک فیدا از مشترک دریافت شد.\n👤 شناسه کاربر: {uid}\n📎 مدرک پیوست شده است.", photo_id, document_id)
    elif mode == "print":
        await _send_to_admins(context.bot, f"{title}\n\n🖨 فایل جدید برای خدمات چاپ دریافت شد.\n👤 شناسه کاربر: {uid}\n📎 فایل پیوست شده است.", photo_id, document_id)
    raise ApplicationHandlerStop


async def _text(update, context):
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})

    # Intentionally no manual "ارسال کد به مدیریت" option here. A code is
    # requested by management from the service notification itself.
    if st.get("mode") == "partner_send_code" and st.get("partner_id"):
        p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (st["partner_id"],)).fetchone()
        if p:
            text = f"👔 مدیر — کد از همکار دریافت شد\n\n👤 همکار: {p['name']}\n📱 شماره: {p['phone']}\n🆔 شناسه تلگرام: {uid}\n🎫 کد: {t}"
            await _send_to_admins(context.bot, text)
            st["mode"] = None
            await update.message.reply_text("✅ کد برای مدیریت ارسال شد.", reply_markup=_partner_keyboard())
            raise ApplicationHandlerStop


def install(app, bot_module):
    global B
    B = bot_module
    B.partner_kb = lambda lang="fa": _partner_keyboard()
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, _media), group=-2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text), group=-2)
