"""Admin controls for the Iranian subscriber menu.

All options are enabled by default. The admin can independently enable/disable
individual Iranian-menu options without touching the main bot router.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

KEYS = (
    ("ir_gov", "🏛 حل مشکل ورود اتباع دولت من"),
    ("ir_track", "🎫 پیگیری"),
    ("ir_wallet", "💰 کیف پول من"),
    ("contact", "📞 تماس با ما"),
    ("complaint", "📝 ثبت شکایت"),
    ("partner", "🔵 👥 پنل همکاران"),
)

def _enabled(B, key):
    return str(B.db.setting("ir_enabled_" + key, "1")).strip().lower() not in {"0", "false", "off", "no"}

def _admin_markup(B):
    rows=[]
    for key,label in KEYS:
        state="🟢 فعال" if _enabled(B,key) else "🔴 غیرفعال"
        rows.append([InlineKeyboardButton(f"{state} | {label}", callback_data=f"iradm:toggle:{key}")])
    rows.append([InlineKeyboardButton("🟢 فعال‌سازی همه", callback_data="iradm:all:on")])
    rows.append([InlineKeyboardButton("🔴 غیرفعال‌سازی همه", callback_data="iradm:all:off")])
    rows.append([InlineKeyboardButton("⬅️ پنل مدیریت", callback_data="adm:menu")])
    return InlineKeyboardMarkup(rows)

def install(app, B):
    if getattr(B, "_iranian_admin_installed", False):
        return
    import telegram_admin_plus as A
    old_menu=A._admin_menu
    def menu():
        base=old_menu()
        rows=list(base.inline_keyboard)
        rows.insert(-1,[InlineKeyboardButton("🇮🇷 مدیریت خدمات بخش ایرانی",callback_data="iradm:menu")])
        return InlineKeyboardMarkup(rows)
    A._admin_menu=menu

    async def cb(update, context):
        q=update.callback_query
        data=str(q.data or "")
        if not data.startswith("iradm:"):
            return
        if not B.admin(q.from_user.id):
            await q.answer("دسترسی ندارید.",show_alert=True)
            raise ApplicationHandlerStop
        await q.answer()
        parts=data.split(":")
        if len(parts)>=2 and parts[1]=="menu":
            await q.message.reply_text("🇮🇷 مدیریت خدمات بخش ایرانی\n\nهر گزینه را جداگانه می‌توانید فعال یا غیرفعال کنید.\nحالت پیش‌فرض همه گزینه‌ها فعال است:",reply_markup=_admin_markup(B))
            raise ApplicationHandlerStop
        if len(parts)==3 and parts[1]=="toggle":
            key=parts[2]
            if key not in {x[0] for x in KEYS}:
                raise ApplicationHandlerStop
            new="0" if _enabled(B,key) else "1"
            B.db.set_setting("ir_enabled_"+key,new)
            await q.message.reply_text(("🟢 فعال شد" if new=="1" else "🔴 غیرفعال شد")+f"\n{dict(KEYS)[key]}",reply_markup=_admin_markup(B))
            raise ApplicationHandlerStop
        if len(parts)==3 and parts[1]=="all":
            new="1" if parts[2]=="on" else "0"
            for key,_ in KEYS: B.db.set_setting("ir_enabled_"+key,new)
            await q.message.reply_text("✅ همه گزینه‌های بخش ایرانی فعال شدند." if new=="1" else "⛔ همه گزینه‌های بخش ایرانی غیرفعال شدند.",reply_markup=_admin_markup(B))
            raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb,pattern=r"^iradm:"),group=-30)
    B._iranian_admin_installed=True
