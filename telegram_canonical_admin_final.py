"""Single authoritative Telegram admin UI and dispatcher.

This module is the final owner of the admin entry point and all ``adm:*``
callbacks. Legacy modules may provide business logic, but they do not own the
visible admin menu or its dispatch path.
"""
import os
import re
import inspect
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

ADMIN_IDS = {"159039104", "7165912028"}
ADMIN_TEXTS = {
    "🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت",
    "🔵 🛠 پنل مدیریت بات", "🔵 🛠 پنل مدیریت"
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
    rows = [
        [("👤 کاربران", "adm:users"), ("👥 همکاران", "adm:partners")],
        [("➕ افزودن همکار", "adm:addpartner")],
        [("🌙 همکاران شب‌کار", "night2:menu")],
        [("🌙 بستن ربات در شب", "adm:night_off"), ("☀️ باز کردن ربات در شب", "adm:night_on")],
        [("📋 درخواست‌ها", "adm:requests"), ("💳 پرداخت‌ها", "adm:payments")],
        [("💰 شارژها", "adm:topups"), ("⚙️ قیمت‌ها", "adm:prices")],
        [("🟢 خدمات", "adm:services")],
        [("💵 افزایش شارژ", "adm:creditup"), ("💸 کاهش شارژ", "adm:creditdown")],
        [("✏️ تغییر متن‌ها", "adm:texts")],
        [("📊 گزارش کامل", "adm:report"), ("📣 اعلان همگانی", "adm:announce")],
        [("🤖 بات‌های متصل", "adm:bots"), ("🧾 لاگ مدیریت", "adm:logs")],
        [("⚙️ تنظیمات", "adm:settings")],
        [("⬅️ منوی اصلی", "adm:main")],
    ]
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows])


def _reset_admin_state(B, uid):
    st = B.S.setdefault(uid, {})
    st.update({"mode": "main", "admin": True, "admin_plus_mode": None, "night_mode": None})
    return st


async def _send_menu(message, B):
    await message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=menu())


async def _entry(update, context, B):
    msg = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if not msg or not user or not _admin(B, user.id):
        return
    if (getattr(msg, "text", "") or "").strip() not in ADMIN_TEXTS:
        return
    _reset_admin_state(B, user.id)
    await _send_menu(msg, B)
    raise ApplicationHandlerStop


async def _callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q or not _admin(B, q.from_user.id):
        return
    data = str(q.data or "")
    if not data.startswith("adm:"):
        return
    try:
        await q.answer()
    except Exception:
        pass

    # ``telegram_admin_plus`` contains the real admin business actions.
    # This owner only controls routing and menu ownership, then stops all
    # lower-priority legacy callback handlers from competing with it.
    try:
        import telegram_admin_plus as A
        result = A._callback(update, context, B)
        if inspect.isawaitable(result):
            await result
    except Exception:
        # Never leave a dead button. Give the admin a deterministic error and
        # a route back to the canonical menu.
        try:
            await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد.\n\nاز منوی مدیریت دوباره انتخاب کنید.", reply_markup=menu())
        except Exception:
            pass
    raise ApplicationHandlerStop


async def _text(update, context, B):
    msg = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if not msg or not user or not _admin(B, user.id):
        return
    # First handle entry into the panel.
    if (getattr(msg, "text", "") or "").strip() in ADMIN_TEXTS:
        _reset_admin_state(B, user.id)
        await _send_menu(msg, B)
        raise ApplicationHandlerStop

    # Admin text continuations (price, credit, text editing, announcement,
    # partner creation, etc.) remain implemented by admin_plus, but are routed
    # here so the legacy module cannot compete for the update.
    try:
        import telegram_admin_plus as A
        result = A._text(update, context, B)
        if inspect.isawaitable(result):
            await result
        # If admin_plus had no active mode it may return without doing anything;
        # in that case do not consume unrelated customer text.
        if B.S.get(user.id, {}).get("admin_plus_mode") is not None:
            raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception:
        # Only consume an admin continuation when one was actually active.
        if B.S.get(user.id, {}).get("admin_plus_mode") is not None:
            try:
                await msg.reply_text("❌ ورود اطلاعات با خطا مواجه شد. دوباره تلاش کنید.", reply_markup=menu())
            except Exception:
                pass
            raise ApplicationHandlerStop


def install(app, B):
    # Idempotent: the runtime can safely call the owner more than once.
    B.amenu = menu
    B.admin_menu_final = menu
    try:
        import telegram_admin_plus as A
        A._admin_menu = menu
    except Exception:
        pass

    if getattr(B, "_canonical_admin_final_v4", False):
        return True

    # Extremely early groups make this the single dispatch owner. Legacy
    # handlers may still be installed for service compatibility, but adm:*
    # updates are stopped before they can compete.
    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^adm:"), group=-100000001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)), group=-100000000)
    B._canonical_admin_final_v4 = True
    return True
