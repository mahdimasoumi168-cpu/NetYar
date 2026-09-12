"""Direct Telegram admin <-> partner communication.

Adds a dedicated admin-panel entry for choosing a partner and starting a
free-form conversation. Text/media delivery is handled by the canonical
telegram_ticket_reliability module after the target partner is selected.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger("netyar.telegram.admin_partner_chat")
BUTTON = "💬 ارتباط با همکار"


def _admin_keyboard_with_contact(original, B):
    rows = [list(row) for row in original(B).inline_keyboard]
    # Keep this option visible in the main management panel without creating
    # a ReplyKeyboard; B.kb is already normalized to inline UI by the project.
    rows.insert(-1 if rows else 0, [InlineKeyboardButton(BUTTON, callback_data="adminpartner:list")])
    return InlineKeyboardMarkup(rows)


def _partners(B):
    return B.db.conn.execute(
        "SELECT id,name,phone,active FROM partners ORDER BY active DESC,id DESC LIMIT 100"
    ).fetchall()


async def _show_partners(update, B):
    q = update.callback_query
    rows = _partners(B)
    if not rows:
        return await q.message.reply_text("👥 هیچ همکاری در پنل ثبت نشده است.")
    buttons = []
    for p in rows:
        name = (p["name"] or "بدون نام").strip()
        phone = (p["phone"] or "-").strip()
        status = "🟢" if p["active"] else "🔴"
        buttons.append([InlineKeyboardButton(
            f"{status} {name} | {phone}",
            callback_data=f"adminpartner:select:{int(p['id'])}",
        )])
    buttons.append([InlineKeyboardButton("❌ بستن", callback_data="adminpartner:close")])
    return await q.message.reply_text(
        "💬 ارتباط با همکار\n\nهمکار موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _select_partner(update, B, pid):
    q = update.callback_query
    uid = q.from_user.id
    if not B.admin(uid):
        return await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
    p = B.db.conn.execute(
        "SELECT id,name,phone,active FROM partners WHERE id=?", (pid,)
    ).fetchone()
    if not p:
        return await q.message.reply_text("❌ همکار پیدا نشد.")
    chat_value = B.db.setting(f"partner_chat_{pid}", "").strip()
    if not chat_value:
        return await q.message.reply_text(
            "❌ چت تلگرام این همکار هنوز ثبت نشده است.\n\n"
            "از همکار بخواهید یک‌بار وارد پنل همکاران ربات شود تا ارتباط او ثبت شود."
        )
    try:
        chat_id = int(chat_value)
    except Exception:
        return await q.message.reply_text("❌ شناسه چت همکار نامعتبر است.")

    st = B.S.setdefault(uid, {})
    st["mode"] = "ticket_admin_reply"
    st["ticket_partner_id"] = pid
    B.db.set_setting(f"ticket_admin_{pid}", str(uid))

    name = (p["name"] or "بدون نام").strip()
    phone = (p["phone"] or "-").strip()
    await q.message.reply_text(
        f"💬 ارتباط با همکار فعال شد.\n\n"
        f"👤 همکار: {name}\n"
        f"📱 موبایل: {phone}\n\n"
        "حالا پیام خود را بفرستید.\n"
        "✍️ متن، 🖼 عکس، 🎥 ویدیو، 🎤 ویس یا 📎 فایل همگی قابل ارسال هستند.\n\n"
        "برای هر پیام جدید لازم نیست دوباره همکار را انتخاب کنید."
    )


async def _callback(update, context, B):
    q = update.callback_query
    data = str(q.data or "")
    if not data.startswith("adminpartner:"):
        return
    await q.answer()
    if not B.admin(q.from_user.id):
        await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
        raise ApplicationHandlerStop
    try:
        if data == "adminpartner:list":
            await _show_partners(update, B)
        elif data == "adminpartner:close":
            await q.message.reply_text("✅ بخش ارتباط با همکار بسته شد.")
        elif data.startswith("adminpartner:select:"):
            pid = int(data.rsplit(":", 1)[1])
            await _select_partner(update, B, pid)
    except Exception:
        log.exception("admin partner chat callback failed")
        await q.message.reply_text("❌ انجام عملیات ارتباط با همکار ناموفق بود.")
    raise ApplicationHandlerStop


async def _entry(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not B.admin(user.id):
        return
    text = (message.text or "").strip()
    if text != BUTTON:
        return
    # This catches the label too, so it remains compatible if another legacy
    # layer turns the inline button back into a visible text callback.
    await message.reply_text("💬 برای شروع ارتباط، همکار موردنظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 انتخاب همکار", callback_data="adminpartner:list")],
    ]))
    raise ApplicationHandlerStop


def install(app, B):
    import telegram_panels as panels
    original = panels.admin_keyboard
    if not getattr(original, "_admin_partner_chat_patched", False):
        def patched_admin_keyboard(B_):
            return _admin_keyboard_with_contact(original, B_)
        patched_admin_keyboard._admin_partner_chat_patched = True
        panels.admin_keyboard = patched_admin_keyboard

    app.add_handler(
        CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^adminpartner:"),
        group=-110,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _entry(u, c, B)),
        group=-109,
    )
