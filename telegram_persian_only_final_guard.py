"""Final Telegram Persian-only/start/restart guard.

Installed last so legacy language/start handlers cannot take control again.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.persian_only")
RESTART = "🔄 شروع مجدد"
USE_SERVICES = "🛎 استفاده از خدمات"
WELCOME = (
    "👋 سلام!\n\n"
    "به سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\n"
    "اینجا تلاش کرده‌ایم خدمات موردنیاز شما را به‌صورت سریع، ساده و آنلاین در اختیارتان قرار دهیم تا بدون سردرگمی بتوانید خدمت موردنظر خود را دریافت یا پیگیری کنید.\n\n"
    "🚀 بات، کمک یار مهاجر؛ خدماتی برای شما، درآمدی برای همه\n\n"
    "📌 برای شروع دریافت خدمات، روی دکمه «🛎 استفاده از خدمات» بزنید."
)

def _restart_kb():
    return ReplyKeyboardMarkup([[RESTART]], resize_keyboard=True, one_time_keyboard=False, is_persistent=True)

def _services_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton(USE_SERVICES, callback_data="start:services")]])

def _set_fa(B, uid, *, keep_partner=True):
    old = dict(B.S.get(uid, {}) or {})
    partner_id = old.get("partner_id") if keep_partner else None
    partner_active = old.get("partner_active", True) if keep_partner else True
    B.S[uid] = {"lang": "fa"}
    if partner_id:
        B.S[uid].update({"partner_id": partner_id, "partner_active": partner_active})
    return B.S[uid]

def install(app=None, B=None, *args, **kwargs):
    if app is None or B is None or getattr(app, "_netyar_persian_only_final", False):
        return

    async def start(update, context):
        uid = update.effective_user.id
        try:
            B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
        except Exception:
            pass
        _set_fa(B, uid, keep_partner=True)
        await update.effective_message.reply_text(WELCOME, reply_markup=_services_kb())
        await update.effective_message.reply_text("👇", reply_markup=_restart_kb())
        raise ApplicationHandlerStop

    async def restart(update, context):
        uid = update.effective_user.id
        _set_fa(B, uid, keep_partner=True)
        await update.effective_message.reply_text(WELCOME, reply_markup=_services_kb())
        raise ApplicationHandlerStop

    async def language_callback(update, context):
        q = update.callback_query
        if not q or not str(q.data or "").startswith("lang:"):
            return
        uid = q.from_user.id
        _set_fa(B, uid, keep_partner=True)
        await q.answer("زبان سامانه فقط فارسی است.")
        await q.message.reply_text("زبان سامانه فقط فارسی است.\n\nلطفاً نوع کاربری خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"), InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian")]]))
        raise ApplicationHandlerStop

    async def services_callback(update, context):
        q = update.callback_query
        if not q or q.data != "start:services":
            return
        uid = q.from_user.id
        st = _set_fa(B, uid, keep_partner=True)
        st["mode"] = None
        await q.answer()
        await q.message.reply_text("نوع کاربری خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم", callback_data="st:foreign"), InlineKeyboardButton("🇮🇷 ایرانی هستم", callback_data="st:iranian")]]))
        raise ApplicationHandlerStop

    app.add_handler(CommandHandler("start", start), group=-10000)
    app.add_handler(MessageHandler(filters.Regex(f"^{RESTART}$"), restart), group=-10000)
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:"), group=-10000)
    app.add_handler(CallbackQueryHandler(services_callback, pattern=r"^start:services$"), group=-9999)
    app._netyar_persian_only_final = True
    B._telegram_persian_only_final = True
    log.info("Telegram Persian-only final guard installed")
