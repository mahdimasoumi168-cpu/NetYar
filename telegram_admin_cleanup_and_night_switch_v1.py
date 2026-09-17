"""Canonical admin-menu cleanup and persistent night-shift switch."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

MARK = "_admin_cleanup_night_switch_v1"
NIGHT_KEY = "night_shift_enabled"


def _admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        return False


def _enabled(B):
    try:
        return str(B.db.setting(NIGHT_KEY, "1") or "1") == "1"
    except Exception:
        return True


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 کاربران", callback_data="adm:users"), InlineKeyboardButton("👥 همکاران", callback_data="adm:partners")],
        [InlineKeyboardButton("➕ افزودن همکار", callback_data="adm:addpartner"), InlineKeyboardButton("🌙 شیفت شب", callback_data="adm:nighttoggle")],
        [InlineKeyboardButton("📋 درخواست‌ها", callback_data="adm:requests"), InlineKeyboardButton("💳 پرداخت‌ها", callback_data="adm:payments")],
        [InlineKeyboardButton("💰 شارژها", callback_data="adm:topups"), InlineKeyboardButton("⚙️ قیمت‌ها", callback_data="adm:prices")],
        [InlineKeyboardButton("🟢 خدمات", callback_data="adm:services"), InlineKeyboardButton("💵 افزایش شارژ", callback_data="adm:creditup")],
        [InlineKeyboardButton("💸 کاهش شارژ", callback_data="adm:creditdown"), InlineKeyboardButton("✏️ تغییر متن‌ها", callback_data="adm:texts")],
        [InlineKeyboardButton("📊 گزارش کامل", callback_data="adm:report"), InlineKeyboardButton("📣 اعلان همگانی", callback_data="adm:announce")],
        [InlineKeyboardButton("🤖 بات‌های متصل", callback_data="adm:bots"), InlineKeyboardButton("🧾 لاگ مدیریت", callback_data="adm:logs")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="adm:settings")],
        [InlineKeyboardButton("⬅️ منوی اصلی", callback_data="adm:main")],
    ])


def _patch_night_gate(B):
    # Existing off-hours modules own the actual access policy. They all expose
    # _is_open; wrap it so the admin switch can disable/enable the night gate
    # without changing the configured 07:00-19:00 working hours.
    names = (
        "telegram_offhours_partner_gate_v2",
        "telegram_absolute_offhours_guard",
        "telegram_persian_offhours_lock",
        "telegram_partner_code_reliable",
        "telegram_management_stability_final",
    )
    for name in names:
        try:
            m = __import__(name)
            original = getattr(m, "_is_open", None)
            if not callable(original) or getattr(m, "_netyar_night_wrapped", False):
                continue
            def wrapped(B_, _orig=original):
                if not _enabled(B_):
                    return True
                return _orig(B_)
            m._is_open = wrapped
            m._netyar_night_wrapped = True
        except Exception:
            continue


async def _callback(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("adm:") or not _admin(B, q.from_user.id):
        return
    action = str(q.data).split(":", 1)[1]
    if action == "menu":
        await q.answer()
        await q.message.reply_text("🛠 پنل مدیریت\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=menu())
        raise ApplicationHandlerStop
    if action != "nighttoggle":
        return
    current = _enabled(B)
    new = "0" if current else "1"
    try:
        B.db.set_setting(NIGHT_KEY, new)
    except Exception:
        await q.answer("ذخیره وضعیت انجام نشد.", show_alert=True)
        raise ApplicationHandlerStop
    _patch_night_gate(B)
    await q.answer("وضعیت شیفت شب تغییر کرد.")
    status = "🟢 فعال" if new == "1" else "🔴 غیرفعال"
    text = (
        f"🌙 کنترل شیفت شب\n\nوضعیت جدید: {status}\n\n"
        "ساعت کاری ۰۷:۰۰ تا ۱۹:۰۰ تغییر نکرده است.\n"
        "این گزینه فقط گیت خارج از ساعت کاری را فعال/غیرفعال می‌کند."
    )
    await q.message.reply_text(text, reply_markup=menu())
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, MARK, False):
        return True
    _patch_night_gate(B)
    try:
        import telegram_admin_ui_final_v2 as A
        A.menu = menu
        A._admin_menu = menu
    except Exception:
        pass
    B.admin_menu_final = menu
    B.amenu = menu
    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^adm:(menu|nighttoggle)$"), group=-40000)
    setattr(B, MARK, True)
    return True
