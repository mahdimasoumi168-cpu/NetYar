"""Deterministic full Telegram admin panel and request management entry point."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

ADMIN_LABELS={"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات","پنل مدیریت"}

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 کاربران",callback_data="adm:users"),InlineKeyboardButton("👥 همکاران",callback_data="adm:partners")],
        [InlineKeyboardButton("➕ افزودن همکار جدید",callback_data="adm:addpartner"),InlineKeyboardButton("🌙 همکاران شب‌کار",callback_data="night2:menu")],
        [InlineKeyboardButton("📋 مدیریت درخواست‌ها",callback_data="adm:reqmanage")],
        [InlineKeyboardButton("💰 شارژها",callback_data="adm:topups"),InlineKeyboardButton("💳 پرداخت‌ها",callback_data="adm:payments")],
        [InlineKeyboardButton("📋 همه درخواست‌ها",callback_data="adm:requests"),InlineKeyboardButton("⚙️ قیمت‌ها",callback_data="adm:prices")],
        [InlineKeyboardButton("➕ افزایش قیمت",callback_data="adm:priceup"),InlineKeyboardButton("➖ کاهش قیمت",callback_data="adm:pricedown")],
        [InlineKeyboardButton("💵 افزایش شارژ",callback_data="adm:creditup"),InlineKeyboardButton("💸 کاهش شارژ",callback_data="adm:creditdown")],
        [InlineKeyboardButton("📈 قیمت‌گذاری تک‌تک خدمات همکار",callback_data="ppx:start")],
        [InlineKeyboardButton("🟢 خدمات",callback_data="adm:services"),InlineKeyboardButton("✏️ تغییر متن‌ها",callback_data="adm:texts")],
        [InlineKeyboardButton("📊 گزارش کامل",callback_data="adm:report"),InlineKeyboardButton("📣 اعلان همگانی",callback_data="adm:announce")],
        [InlineKeyboardButton("🤖 بات‌های متصل",callback_data="adm:bots"),InlineKeyboardButton("🧾 لاگ مدیریت",callback_data="adm:logs")],
        [InlineKeyboardButton("⚙️ تنظیمات",callback_data="adm:settings"),InlineKeyboardButton("🧩 ابزارهای مدیریتی",callback_data="adm:tools")],
        [InlineKeyboardButton("⬅️ منوی اصلی",callback_data="adm:main")],
        [InlineKeyboardButton("🚪 خروج کامل از مدیریت",callback_data="adm:exit")],
    ])

def _request_list(B):
    rows=B.db.conn.execute("SELECT id,tracking_code,service_key,status,amount,created_at FROM requests ORDER BY id DESC LIMIT 25").fetchall()
    buttons=[]
    for r in rows:
        buttons.append([InlineKeyboardButton(f"#{r['id']} | {r['tracking_code']} | {str(r['status'])[:12]}",callback_data=f"panel:req:{int(r['id'])}")])
    buttons.append([InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")])
    return InlineKeyboardMarkup(buttons)

async def _controls(update,context,B):
    q=update.callback_query
    if not q or not str(q.data or "").startswith("adm:") or not B.admin(q.from_user.id): return
    action=str(q.data).split(":",1)[1]
    if action=="menu":
        await q.answer();await q.message.reply_text("🛠 پنل مدیریت کامل\n\nبخش موردنظر را انتخاب کنید:",reply_markup=menu());raise ApplicationHandlerStop
    if action=="reqmanage":
        await q.answer();await q.message.reply_text("📋 مدیریت درخواست‌ها\n\nدرخواست را انتخاب کنید. کنترل‌های مشاهده کامل، بررسی، انجام، رد، پاسخ و درخواست کد از همکار در صفحه هر درخواست فعال است:",reply_markup=_request_list(B));raise ApplicationHandlerStop
    if action=="tools":
        await q.answer();await q.message.reply_text("🧩 ابزارهای مدیریتی",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 مدیریت درخواست‌ها",callback_data="adm:reqmanage")],[InlineKeyboardButton("📈 قیمت‌گذاری همکار",callback_data="ppx:start")],[InlineKeyboardButton("📣 اعلان همگانی",callback_data="adm:announce")],[InlineKeyboardButton("🧾 لاگ مدیریت",callback_data="adm:logs")],[InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="adm:menu")]]));raise ApplicationHandlerStop


def install(app,B):
    if getattr(B,"_final_admin_menu_fix",False): return True
    import telegram_admin_plus as A
    A._admin_menu=menu;B.amenu=menu
    async def admin_text(update,context):
        msg=getattr(update,"effective_message",None);user=getattr(update,"effective_user",None)
        if not msg or not user or not B.admin(user.id):return
        if (msg.text or "").strip() not in ADMIN_LABELS:return
        await msg.reply_text("🛠 پنل مدیریت کامل\n\n👤 کاربران | 👥 همکاران | 📋 درخواست‌ها | 💰 شارژ و پرداخت\n⚙️ قیمت‌ها | 🟢 خدمات | 📊 گزارش | 📣 اعلان\n\nبخش موردنظر را انتخاب کنید:",reply_markup=menu());raise ApplicationHandlerStop
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,admin_text),group=-20000)
    app.add_handler(CallbackQueryHandler(_controls,pattern=r"^adm:(menu|reqmanage|tools)$"),group=-20000)
    B._final_admin_menu_fix=True
    return True
