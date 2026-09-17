"""NetYar final Telegram callback owner v42.

Owns ui2 callbacks before all legacy routers. Lookup failures are recovered
from the message markup and are never allowed to fall through to the old
"option not executed" handlers.
"""
import inspect
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.ui_absolute_v42")
TRUST = {"🛡 اعتماد", "🛡️ اعتماد"}
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SITE_URL = "https://netyarmohajer.sizpay.ir"
ALIASES = {
    "🎫 درخواست‌های من": "📋 سوابق",
    "📨 ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "✉️ ارسال تیکت به مدیریت": "🎫 تیکت به مدیریت",
    "✉️ ارسال پیام به مدیریت": "💬 ارتباط با مدیریت",
    "📝 ثبت شکایت": "📝 ثبت شکایت مشتریان",
    "🪪 حل مشکل ورود اتباع دولت من": "🪪 فیدای غیر حضوری",
}

def rv(row, key, index):
    if row is None: return None
    try: return row[key]
    except Exception: pass
    try: return row[index]
    except Exception: return None

def recover_label(q, data):
    try:
        for row in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
            for b in row or []:
                if str(getattr(b, "callback_data", "") or "") == data:
                    return str(getattr(b, "text", "") or "").strip()
    except Exception:
        log.exception("v42 label recovery failed")
    return ""

async def trust(q):
    await q.message.reply_text(
        "🛡 نماد اعتماد الکترونیکی\n\n"
        "🏢 نام کسب‌وکار: نت یار مهاجر\n"
        "🔤 نام لاتین: NetYareMohajer\n"
        "🌐 دامنه: netyarmohajer.sizpay.ir\n"
        "☎️ تلفن: 03135674350\n"
        "📧 ایمیل: netyaremohajer@gmail.com",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده نماد در eNAMAD", url=TRUST_URL)],
            [InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر", url=SITE_URL)],
            [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی", callback_data="iranian:back")],
        ]), disable_web_page_preview=True)

def install(app, B):
    if getattr(B, "_absolute_ui_owner_v42", False): return

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        data = str(getattr(q, "data", "") or "") if q else ""
        if not q or not data.startswith("ui2:"): return
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        label = ""
        try:
            token = data[4:]
            row = None
            try:
                row = B.db.conn.execute(
                    "SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)
                ).fetchone()
            except Exception:
                log.exception("v42 ui2 database lookup failed")
            owner = rv(row, "user_id", 0)
            if owner and str(owner) != str(uid):
                await q.answer("این دکمه متعلق به حساب دیگری است.", show_alert=True)
                raise ApplicationHandlerStop
            label = str(rv(row, "label", 1) or "").strip()
            lang = rv(row, "lang", 2); status = rv(row, "status", 3)
            if lang: st["lang"] = lang
            if status: st["status"] = status
            if not label: label = recover_label(q, data)
            if not label:
                await q.answer("این دکمه منقضی شده است؛ لطفاً منو را دوباره باز کنید.", show_alert=True)
                raise ApplicationHandlerStop
            label = ALIASES.get(label, label)
            try: await q.answer()
            except Exception: pass

            if label in TRUST:
                await trust(q); raise ApplicationHandlerStop
            if label == "🏛 خدمات ایرانی":
                st["status"] = "iranian"; st["mode"] = None
                import telegram_final_iranian_menu_v38 as I
                await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=I._keyboard(B, uid))
                raise ApplicationHandlerStop

            import telegram_ui_policy_v2 as UI
            result = UI._dispatch(update, context, B, label)
            if inspect.isawaitable(result): await result
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("v42 callback failed label=%r data=%r", label, data)
            try:
                import telegram_absolute_callback_hardening_v30 as V30
                result = V30._dispatch(update, context, B, label)
                if inspect.isawaitable(result): await result
                raise ApplicationHandlerStop
            except ApplicationHandlerStop:
                raise
            except Exception:
                log.exception("v42 secondary dispatch failed label=%r", label)
                try:
                    markup = B.partner_kb(st.get("lang", "fa")) if st.get("partner_id") and st.get("partner_active") and not st.get("partner_logged_out") else B.main(uid)
                    await q.message.reply_text("❌ اجرای گزینه با خطای داخلی مواجه شد؛ وضعیت شما حفظ شد. لطفاً دوباره همان گزینه را انتخاب کنید.", reply_markup=markup)
                except Exception: log.exception("v42 recovery reply failed")
                raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-5000000)
    B._absolute_ui_owner_v42 = True
    log.info("ABSOLUTE Telegram ui2 callback owner v42 installed")
