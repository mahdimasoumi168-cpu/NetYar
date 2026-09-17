"""Final Telegram admin UI owner.

One canonical admin panel: no duplicate management buttons, and the partner
creation entry point is handled before legacy admin routers. Other admin
callbacks continue to their existing feature owners.
"""
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

_MARK = "_telegram_admin_ui_final_v2"


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        return False


def menu():
    rows = [
        [("👤 کاربران", "adm:users"), ("👥 همکاران", "adm:partners")],
        [("➕ افزودن همکار", "adm:addpartner"), ("💰 شارژها", "adm:topups")],
        [("📋 درخواست‌ها", "adm:requests"), ("💳 پرداخت‌ها", "adm:payments")],
        [("⚙️ قیمت‌ها", "adm:prices"), ("🟢 خدمات", "adm:services")],
        [("💵 افزایش شارژ", "adm:creditup"), ("💸 کاهش شارژ", "adm:creditdown")],
        [("✏️ تغییر متن‌ها", "adm:texts"), ("📊 گزارش کامل", "adm:report")],
        [("📣 اعلان همگانی", "adm:announce"), ("🤖 بات‌های متصل", "adm:bots")],
        [("🧾 لاگ مدیریت", "adm:logs"), ("⚙️ تنظیمات", "adm:settings")],
        [("⬅️ منوی اصلی", "adm:main")],
    ]
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in r] for r in rows])


async def _callback(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("adm:"):
        return
    uid = q.from_user.id
    if not _admin(B, uid):
        await q.answer("دسترسی ندارید.", show_alert=True)
        raise ApplicationHandlerStop
    data = str(q.data)
    if data == "adm:menu":
        await q.answer()
        B.S.setdefault(uid, {})["admin_plus_mode"] = None
        await q.message.reply_text("🛠 پنل مدیریت\n\nبخش موردنظر را انتخاب کنید:", reply_markup=menu())
        raise ApplicationHandlerStop
    if data == "adm:addpartner":
        await q.answer()
        st = B.S.setdefault(uid, {})
        st["admin_plus_mode"] = "add_partner"
        await q.message.reply_text(
            "➕ افزودن همکار\n\nفرمت را دقیقاً این‌طور ارسال کنید:\nشماره | رمز | نام همکار\n\nمثال:\n09xxxxxxxxx | رمز جدید | همکار اصفهان",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="adm:menu")]])
        )
        raise ApplicationHandlerStop
    # Legacy admin_plus owns all other adm:* callbacks.


async def _text(update, context, B):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not _admin(B, user.id):
        return
    st = B.S.setdefault(user.id, {})
    if st.get("admin_plus_mode") != "add_partner":
        return
    text = str(msg.text or "").strip()
    if text in {"❌ لغو", "لغو", "انصراف", "❌ انصراف", "⬅️ پنل مدیریت"}:
        st["admin_plus_mode"] = None
        await msg.reply_text("لغو شد.", reply_markup=menu())
        raise ApplicationHandlerStop
    parts = [x.strip() for x in text.split("|")]
    if len(parts) != 3 or not all(parts):
        await msg.reply_text("❌ فرمت نادرست است.\n\nشماره | رمز | نام همکار", reply_markup=menu())
        raise ApplicationHandlerStop
    phone = re.sub(r"\D", "", _digits(parts[0]))
    if phone.startswith("98"):
        phone = "0" + phone[2:]
    if not re.fullmatch(r"09\d{9}", phone):
        await msg.reply_text("❌ شماره موبایل معتبر نیست.", reply_markup=menu())
        raise ApplicationHandlerStop
    try:
        B.db.add_partner(phone, parts[1], parts[2])
        st["admin_plus_mode"] = None
        await msg.reply_text(f"✅ همکار «{parts[2]}» با موفقیت اضافه شد.", reply_markup=menu())
    except Exception:
        await msg.reply_text("❌ ثبت همکار انجام نشد؛ شماره احتمالاً قبلاً ثبت شده است.", reply_markup=menu())
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, _MARK, False):
        return
    # Expose the single canonical menu to any final UI layer that asks for it.
    B.admin_menu_final = menu
    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^adm:"), group=-30001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _text(u, c, B)), group=-30001)
    setattr(B, _MARK, True)
