"""Canonical admin-menu cleanup and persistent night-shift switch."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

MARK = "_admin_cleanup_night_switch_v2"
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
        [InlineKeyboardButton("➕ افزودن همکار", callback_data="adm:addpartner")],
        [InlineKeyboardButton("🌙 بستن ربات در شب", callback_data="adm:night_off"), InlineKeyboardButton("☀️ باز کردن ربات در شب", callback_data="adm:night_on")],
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


async def _set_night(B, q, enabled):
    try:
        B.db.set_setting(NIGHT_KEY, "1" if enabled else "0")
        _patch_night_gate(B)
    except Exception:
        await q.answer("ذخیره وضعیت انجام نشد.", show_alert=True)
        raise ApplicationHandlerStop
    status = "🟢 باز" if enabled else "🔴 بسته"
    await q.answer("تنظیم شد")
    await q.message.reply_text(
        f"🌙 کنترل ربات در شب\n\nوضعیت: {status}\n\n"
        "⏰ ساعت کاری روزانه همچنان ۰۷:۰۰ تا ۱۹:۰۰ است.\n"
        "این دکمه فقط اجازه یا عدم اجازه فعالیت خارج از ساعت کاری را کنترل می‌کند.",
        reply_markup=menu(),
    )
    raise ApplicationHandlerStop


async def _callback(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("adm:") or not _admin(B, q.from_user.id):
        return
    action = str(q.data).split(":", 1)[1]
    if action == "menu":
        await q.answer()
        await q.message.reply_text("🛠 پنل مدیریت\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=menu())
        raise ApplicationHandlerStop
    if action == "nighttoggle":
        return await _set_night(B, q, not _enabled(B))
    if action == "night_on":
        return await _set_night(B, q, True)
    if action == "night_off":
        return await _set_night(B, q, False)
    return


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
    app.add_handler(
        CallbackQueryHandler(
            lambda u, c: _callback(u, c, B),
            pattern=r"^adm:(menu|nighttoggle|night_on|night_off)$",
        ),
        group=-40000,
    )
    setattr(B, MARK, True)
    return True
