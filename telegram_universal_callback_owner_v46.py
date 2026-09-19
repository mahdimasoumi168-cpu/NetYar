"""Universal Telegram callback owner v49.

A ui2 token is still protected, but a token shown on the callback's current
inline keyboard is accepted even when its persisted owner is stale. This fixes
buttons that were rendered for a previous session/account while retaining the
owner check for callbacks not present on the current message.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.universal_owner_v49")
ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق", "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت", "📝 ثبت شکایت": "📝 انتقادات یا پیشنهادات", "📝 ثبت شکایت مشتریان": "📝 انتقادات یا پیشنهادات",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 فیدای غیر حضوری", "🔵 👥 پنل همکاران": "👥 پنل همکاران",
    "👥 Partner panel": "👥 پنل همکاران", "👥 لوحة الشركاء": "👥 پنل همکاران",
    "🛠 پنل مدیریت": "🛠 پنل مدیریت بات",
}
KNOWN = {
    "➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من", "🔎 پیگیری کد", "📋 سوابق", "💰 موجودی", "💰 کیف پول من",
    "🪪 فیدای غیر حضوری", "🪪 حل مشکل ورود اتباع دولت من",
    "📱 حل مشکل سیم کارت ایرانسل", "🎫 تیکت به مدیریت", "💬 ارتباط با مدیریت", "🚪 خروج از پنل", "❌ انصراف",
    "🔄 شروع مجدد", "🔄 شروع دوباره", "👥 پنل همکاران", "🛠 پنل مدیریت بات", "🎫 پیگیری", "📞 تماس با ما", "📝 ثبت شکایت مشتریان", "📝 انتقادات یا پیشنهادات",
}

def _current_button_label(q, data):
    try:
        for row in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
            for button in row or []:
                if str(getattr(button, "callback_data", "") or "") == data:
                    return str(getattr(button, "text", "") or "").strip()
    except Exception:
        pass
    return ""

def _label(q, B):
    data = str(getattr(q, "data", "") or "")
    current = _current_button_label(q, data)
    if current:
        return current
    if data.startswith("ui2:"):
        try:
            token = data[4:]
            row = B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)).fetchone()
            if row:
                owner = str(row["user_id"] or "")
                if owner and owner != str(q.from_user.id):
                    return "__FORBIDDEN__"
                return str(row["label"] or "").strip()
        except Exception:
            log.exception("ui2 label lookup failed")
    return ""

async def callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q: return
    data = str(getattr(q, "data", "") or "")
    if data == "iranian:back":
        try:
            import telegram_ui_absolute_owner_v43 as UI; await UI._iranian_back(q, B)
        except Exception:
            await q.answer(); await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=B.main(q.from_user.id))
        raise ApplicationHandlerStop
    if not data.startswith("ui2:"): return
    label = ALIASES.get(_label(q, B), _label(q, B))
    if not label: return
    if label == "__FORBIDDEN__":
        await q.answer("این دکمه دیگر مربوط به منوی فعال شما نیست؛ لطفاً از منوی فعلی استفاده کنید.", show_alert=True)
        raise ApplicationHandlerStop
    try: await q.answer()
    except Exception: pass
    if label in KNOWN:
        try:
            from telegram_stable_callback import handle
            await handle(update, context, B, label); raise ApplicationHandlerStop
        except ApplicationHandlerStop: raise
        except Exception: log.exception("stable route failed label=%r", label)
    try:
        import telegram_ui_policy_v2 as UI
        fn=getattr(UI,"_dispatch",None)
        if fn:
            result=await fn(update,context,B,label)
            if result is not None: raise ApplicationHandlerStop
    except ApplicationHandlerStop: raise
    except Exception: log.exception("canonical route failed label=%r",label)
    uid=q.from_user.id; st=B.S.setdefault(uid,{})
    markup=B.partner_kb(st.get("lang","fa")) if st.get("partner_id") and st.get("partner_active",True) else B.main(uid)
    await q.message.reply_text("⛔ این گزینه در منوی فعلی شناخته نشد؛ لطفاً از منوی فعلی استفاده کنید.",reply_markup=markup)
    raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_universal_callback_owner_v49",False): return
    async def _bound(update,context): return await callback(update,context,B)
    app.add_handler(CallbackQueryHandler(_bound,pattern=r"^(ui2:|iranian:back)"),group=-8000000)
    B._universal_callback_owner_v49=True
    log.info("UNIVERSAL Telegram callback owner v49 installed")
