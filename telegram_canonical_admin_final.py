"""Absolute canonical Telegram admin panel owner.

This is the single source of truth for the admin reply-keyboard entry and
canonical inline admin menu. It deliberately uses an extremely early handler
group and an authoritative admin-id fallback so legacy layers cannot replace
this panel for configured administrators.
"""
import os
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

ADMIN_IDS = {"159039104", "7165912028"}
ADMIN_TEXTS = {
    "🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت",
    "🔵 🛠 پنل مدیریت بات", "🔵 🛠 پنل مدیریت",
}


def _admin(B, uid):
    sid = str(uid)
    configured = set()
    for key in ("ADMIN_IDS", "ADMIN_ID_1", "ADMIN_ID_2", "TELEGRAM_ADMIN_IDS"):
        configured.update(x.strip() for x in re.split(r"[;,\s]+", os.getenv(key, "")) if x.strip())
    if sid in ADMIN_IDS or sid in configured:
        return True
    try:
        return bool(B.admin(uid))
    except Exception:
        return False


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 کاربران", callback_data="adm:users"), InlineKeyboardButton("👥 همکاران", callback_data="adm:partners")],
        [InlineKeyboardButton("➕ افزودن همکار", callback_data="adm:addpartner")],
        [InlineKeyboardButton("🌙 همکاران شب‌کار", callback_data="night2:menu")],
        [InlineKeyboardButton("🌙 بستن ربات در شب", callback_data="adm:night_off"), InlineKeyboardButton("☀️ باز کردن ربات در شب", callback_data="adm:night_on")],
        [InlineKeyboardButton("📋 درخواست‌ها", callback_data="adm:requests"), InlineKeyboardButton("💳 پرداخت‌ها", callback_data="adm:payments")],
        [InlineKeyboardButton("💰 شارژها", callback_data="adm:topups"), InlineKeyboardButton("⚙️ قیمت‌ها", callback_data="adm:prices")],
        [InlineKeyboardButton("🟢 خدمات", callback_data="adm:services")],
        [InlineKeyboardButton("💵 افزایش شارژ", callback_data="adm:creditup"), InlineKeyboardButton("💸 کاهش شارژ", callback_data="adm:creditdown")],
        [InlineKeyboardButton("✏️ تغییر متن‌ها", callback_data="adm:texts")],
        [InlineKeyboardButton("📊 گزارش کامل", callback_data="adm:report"), InlineKeyboardButton("📣 اعلان همگانی", callback_data="adm:announce")],
        [InlineKeyboardButton("🤖 بات‌های متصل", callback_data="adm:bots"), InlineKeyboardButton("🧾 لاگ مدیریت", callback_data="adm:logs")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="adm:settings")],
        [InlineKeyboardButton("⬅️ منوی اصلی", callback_data="adm:main")],
    ])


async def _text(update, context, B):
    msg = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if not msg or not user or not _admin(B, user.id):
        return
    if (getattr(msg, "text", "") or "").strip() not in ADMIN_TEXTS:
        return
    st = B.S.setdefault(user.id, {})
    st.clear()
    st.update({"mode": "main", "admin_plus_mode": None, "night_mode": None})
    await msg.reply_text("🛠 پنل مدیریت\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=menu())
    raise ApplicationHandlerStop


async def _callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q or not _admin(B, q.from_user.id):
        return
    if str(q.data or "") != "adm:menu":
        return
    await q.answer()
    st = B.S.setdefault(q.from_user.id, {})
    st.update({"mode": "main", "admin_plus_mode": None, "night_mode": None})
    await q.message.reply_text("🛠 پنل مدیریت\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=menu())
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_canonical_admin_final_v2", False):
        return True
    B.amenu = menu
    B.admin_menu_final = menu
    try:
        import telegram_admin_ui_final_v2 as A
        A.menu = menu
        A._admin_menu = menu
    except Exception:
        pass
    # Must be earlier than every legacy handler. This module is installed last
    # in entrypoint.py, so no later layer can register a lower group.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)), group=-1000000)
    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^adm:menu$"), group=-1000001)
    B._canonical_admin_final_v2 = True
    return True
