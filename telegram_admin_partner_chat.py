"""Direct Telegram admin <-> partner communication."""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger("netyar.telegram.admin_partner_chat")
BUTTON = "💬 ارتباط با همکار"


def _add_button(markup, B=None):
    try:
        from telegram import ReplyKeyboardMarkup
        if isinstance(markup, ReplyKeyboardMarkup):
            rows = [list(row) for row in markup.keyboard]
            if not any(BUTTON in [str(x) for x in row] for row in rows):
                rows.insert(max(0, len(rows) - 1), [BUTTON])
            return ReplyKeyboardMarkup(rows, resize_keyboard=True)
    except Exception:
        pass
    if isinstance(markup, InlineKeyboardMarkup):
        rows = [list(row) for row in markup.inline_keyboard]
        if not any(any(getattr(btn, "text", "") == BUTTON for btn in row) for row in rows):
            rows.insert(max(0, len(rows) - 1), [InlineKeyboardButton(BUTTON, callback_data="adminpartner:list")])
        return InlineKeyboardMarkup(rows)
    return markup


def _partners(B):
    return B.db.conn.execute("SELECT id,name,phone,active FROM partners ORDER BY active DESC,id DESC LIMIT 100").fetchall()


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
        buttons.append([InlineKeyboardButton(f"{status} {name} | {phone}", callback_data=f"adminpartner:select:{int(p['id'])}")])
    buttons.append([InlineKeyboardButton("❌ بستن", callback_data="adminpartner:close")])
    return await q.message.reply_text("💬 ارتباط با همکار\n\nهمکار موردنظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))


async def _select_partner(update, B, pid):
    q = update.callback_query
    uid = q.from_user.id
    if not B.admin(uid):
        return await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
    p = B.db.conn.execute("SELECT id,name,phone,active FROM partners WHERE id=?", (pid,)).fetchone()
    if not p:
        return await q.message.reply_text("❌ همکار پیدا نشد.")
    chat_value = B.db.setting(f"partner_chat_{pid}", "").strip()
    if not chat_value:
        phone = str(p["phone"] or "").strip()
        if phone:
            chat_value = B.db.setting(f"partner_chat_{phone}", "").strip()
    if not chat_value:
        return await q.message.reply_text("❌ چت تلگرام این همکار هنوز ثبت نشده است.\n\nاز همکار بخواهید یک‌بار وارد پنل همکاران ربات شود تا ارتباط او ثبت شود.")
    try:
        int(chat_value)
    except Exception:
        return await q.message.reply_text("❌ شناسه چت همکار نامعتبر است.")
    st = B.S.setdefault(uid, {})
    st["mode"] = "ticket_admin_reply"
    st["ticket_partner_id"] = pid
    B.db.set_setting(f"partner_chat_{pid}", str(chat_value))
    B.db.set_setting(f"ticket_admin_{pid}", str(uid))
    await q.message.reply_text(f"💬 ارتباط با همکار فعال شد.\n\n👤 همکار: {(p['name'] or 'بدون نام').strip()}\n📱 موبایل: {(p['phone'] or '-').strip()}\n\nحالا پیام خود را بفرستید.\n✍️ متن، 🖼 عکس، 🎥 ویدیو، 🎤 ویس یا 📎 فایل همگی قابل ارسال هستند.")


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
            await _select_partner(update, B, int(data.rsplit(":", 1)[1]))
    except Exception:
        log.exception("admin partner chat callback failed")
        await q.message.reply_text("❌ انجام عملیات ارتباط با همکار ناموفق بود.")
    raise ApplicationHandlerStop


async def _entry(update, context, B):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not B.admin(user.id):
        return
    if (message.text or "").strip() != BUTTON:
        return
    await message.reply_text("💬 برای شروع ارتباط، همکار موردنظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 انتخاب همکار", callback_data="adminpartner:list")]]))
    raise ApplicationHandlerStop


def install(app, B):
    try:
        import telegram_panels as panels
        original = panels.admin_keyboard
        if not getattr(original, "_admin_partner_chat_patched", False):
            def patched_admin_keyboard(B_):
                return _add_button(original(B_), B_)
            patched_admin_keyboard._admin_partner_chat_patched = True
            panels.admin_keyboard = patched_admin_keyboard
    except Exception:
        log.exception("could not patch telegram panel keyboard")

    try:
        import admin_control_v5 as A
        original_menu = A.menu
        if not getattr(original_menu, "_admin_partner_chat_patched", False):
            def patched_menu(B_):
                return _add_button(original_menu(B_), B_)
            patched_menu._admin_partner_chat_patched = True
            A.menu = patched_menu
    except Exception:
        log.exception("could not patch v5 admin menu")

    # B.amenu is the function actually used by several later admin handlers.
    # Patch it here too, otherwise a later legacy module can silently replace
    # the visible menu and make the button appear/disappear between clicks.
    try:
        original_amenu = getattr(B, "amenu", None)
        if original_amenu and not getattr(original_amenu, "_admin_partner_chat_patched", False):
            def patched_amenu(*args, **kwargs):
                return _add_button(original_amenu(*args, **kwargs), B)
            patched_amenu._admin_partner_chat_patched = True
            B.amenu = patched_amenu
    except Exception:
        log.exception("could not patch B.amenu")

    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^adminpartner:"), group=-110)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _entry(u, c, B)), group=-109)
