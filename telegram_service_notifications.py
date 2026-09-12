"""Service notifications and partner-code intake for Telegram.

Keeps the canonical bot flow intact while ensuring managers receive a clear
notification plus the submitted document/photo whenever a service reaches a
submission point. Partners can also send a tracking/service code directly to
management.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters

log = logging.getLogger("netyar.telegram.notifications")


def _admin_markup(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"),
         InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"),
         InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])


def _partner_keyboard(B):
    return B.kb([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        ["🎫 درخواست‌های من", "🔎 پیگیری کد"],
        ["📋 سوابق", "💰 موجودی"],
        ["📨 ارسال کد به مدیریت"],
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
        return None

    # Let the canonical bot persist the request/file first. This handler only
    # adds the manager notification; it does not replace the service flow.
    before = B.db.conn.execute(
        "SELECT id,tracking_code FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (st.get("partner_id") or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name),),
    ).fetchone()
    await B.media(update, context)

    after = B.db.conn.execute(
        "SELECT id,tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (st.get("partner_id") or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name),),
    ).fetchone()

    photo_id = update.message.photo[-1].file_id if update.message.photo else None
    document_id = update.message.document.file_id if update.message.document else None
    title = "👔 مدیر — اعلان خدمات جدید"

    if mode == "gov_photo" and after and (not before or after["id"] != before["id"]):
        text = (
            f"{title}\n\n🆕 درخواست حل مشکل سامانه دولت من\n"
            f"🎫 کد پیگیری: {after['tracking_code']}\n"
            f"👤 کاربر: {uid}\n"
            f"🪪 نوع مدرک: {st.get('gov_doc_type', '-')}\n"
            f"📱 موبایل مشترک: {st.get('phone', '-')}\n"
            f"🎂 تاریخ تولد: {st.get('dob', '-')}\n"
            f"🆔 شناسه یکتا: {st.get('unique_id', '-')}\n"
            f"🔖 شناسه اختصاصی: {st.get('special_id', '-')}\n"
            f"🛂 پاسپورت: {st.get('passport', '-') }\n\n"
            "📎 مدرک مشترک در همین اعلان ارسال شده است."
        )
        await _send_to_admins(context.bot, text, photo_id, document_id, after["id"])
    elif mode == "fida_doc":
        text = (
            f"{title}\n\n📄 مدرک فیدا از مشترک دریافت شد.\n"
            f"👤 کاربر: {uid}\n📱 مرحله: دریافت مدرک اولیه\n\n"
            "📎 تصویر/فایل مدرک پیوست شده است."
        )
        await _send_to_admins(context.bot, text, photo_id, document_id)
    elif mode == "print":
        text = (
            f"{title}\n\n🖨 فایل جدید برای خدمات چاپ دریافت شد.\n"
            f"👤 کاربر: {uid}\n📎 فایل پیوست شده است."
        )
        await _send_to_admins(context.bot, text, photo_id, document_id)
    return None


async def _text(update, context):
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if t == "📨 ارسال کد به مدیریت":
        if not st.get("partner_id"):
            return None
        st["mode"] = "partner_send_code"
        await update.message.reply_text(
            "🎫 کد پیگیری/کد خدمت را برای مدیریت ارسال کنید:",
            reply_markup=B.cancel_kb(),
        )
        return None
    if st.get("mode") == "partner_send_code":
        if not st.get("partner_id"):
            return None
        p = B.db.conn.execute(
            "SELECT name,phone FROM partners WHERE id=?", (st["partner_id"],)
        ).fetchone()
        if not p:
            return None
        text = (
            "👔 مدیر — کد از همکار دریافت شد\n\n"
            f"👤 همکار: {p['name']}\n📱 شماره: {p['phone']}\n"
            f"🆔 شناسه تلگرام: {uid}\n🎫 کد: {t}"
        )
        await _send_to_admins(context.bot, text)
        st["mode"] = None
        await update.message.reply_text("✅ کد برای مدیریت ارسال شد.", reply_markup=_partner_keyboard(B))
        return None
    return None


def install(app, bot_module):
    global B
    B = bot_module
    B.partner_kb = lambda lang="fa": _partner_keyboard(B)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, _media), group=-2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text), group=-2)
