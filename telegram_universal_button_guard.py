"""Final Telegram button/router guard.

One canonical callback path for inline buttons, with aliases for legacy labels,
and a private admin<->partner reply callback.  This layer is intentionally
installed last so older UI patches cannot leave a visible button without a
working route.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.universal_button_guard")

ALIASES = {
    # Partner panel
    "✉️ تیکت به مدیریت": "✉️ ارسال تیکت به مدیریت",
    "📝 تیکت به مدیریت": "✉️ ارسال تیکت به مدیریت",
    "💬 تیکت به مدیریت": "✉️ ارسال تیکت به مدیریت",
    "✉️ Ticket to management": "✉️ ارسال تیکت به مدیریت",
    "📝 Ticket to management": "✉️ ارسال تیکت به مدیریت",
    "👥 Partner panel": "👥 پنل همکاران",
    "👥 لوحة الشركاء": "👥 پنل همکاران",
    "🎫 Tracking": "🎫 پیگیری",
    "🎫 المتابعة": "🎫 پیگیری",
    "🚪 Exit panel": "🚪 خروج از پنل",
    "➕ Add balance": "➕ شارژ حساب",
    "💰 My balance": "💰 موجودی",
    "📋 History": "📋 سوابق",
    "🔎 Track code": "🔎 پیگیری کد",
    # Main menu legacy variants
    "🪪 فیدا": "🪪 فیدای غیر حضوری",
    "🏛 حل مشکل ورود اتباع دولت من": "🪪 حل مشکل ورود اتباع دولت من",
    "🏛 حل مشکل سامانه دولت من": "🏛 حل مشکل سامانه دولت من",
    "📝 آزمون غربالگری و پیگیری": "📝 آزمون غربالگری",
    "📝 Screening & follow-up": "📝 آزمون غربالگری",
    "🪪 FIDA service": "🪪 فیدای غیر حضوری",
    "🖨 Printing": "🖨 خدمات چاپ",
    "📱 SIM services": "📱 خدمات سیم کارت",
    "📞 Contact us": "📞 تماس با ما",
    "🎫 Card renewal tracking": "🎫 کد رهگیری تمدید کارت‌ها",
    "📝 Customer complaint": "📝 ثبت شکایت مشتریان",
}


def _clean(s):
    s = str(s or "").strip()
    for p in ("🟦 ", "🟩 ", "🟨 ", "🔵 "):
        if s.startswith(p):
            s = s[len(p):].strip()
    return s


def _button_text(q):
    try:
        markup = getattr(q.message, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", []) or []:
            for b in row:
                if str(getattr(b, "callback_data", "")) == str(q.data or ""):
                    return _clean(getattr(b, "text", ""))
    except Exception:
        log.exception("could not recover inline button text")
    return ""


async def _callback(update, context, B):
    q = update.callback_query
    data = str(q.data or "")
    if data.startswith("ticket:reply:"):
        await q.answer()
        if not B.admin(q.from_user.id):
            await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
            raise ApplicationHandlerStop
        try:
            pid = int(data.rsplit(":", 1)[1])
            row = B.db.conn.execute("SELECT id,name,phone FROM partners WHERE id=?", (pid,)).fetchone()
            if not row:
                await q.message.reply_text("❌ همکار پیدا نشد.")
                raise ApplicationHandlerStop
            chat = B.db.setting(f"partner_chat_{pid}", "").strip()
            if not chat and row["phone"]:
                chat = B.db.setting(f"partner_chat_{row['phone']}", "").strip()
            if not chat:
                await q.message.reply_text("❌ چت تلگرام این همکار هنوز ثبت نشده است.")
                raise ApplicationHandlerStop
            st = B.S.setdefault(q.from_user.id, {})
            st.update({"admin": True, "mode": "ticket_admin_reply", "ticket_partner_id": pid})
            await q.message.reply_text(
                f"💬 پاسخ به همکار فعال شد.\n\n👤 {row['name'] or 'بدون نام'}\n📱 {row['phone'] or '-'}\n\nپیام خود را ارسال کنید.\n❌ برای لغو، «انصراف» را بزنید.",
                reply_markup=B.kb([[B.CANCEL]]),
            )
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("ticket reply callback failed")
            await q.message.reply_text("❌ فعال‌سازی پاسخ به همکار ناموفق بود.")
        raise ApplicationHandlerStop

    if not data.startswith("ik:"):
        return
    await q.answer()
    text = _button_text(q)
    if not text:
        await q.message.reply_text("❌ این دکمه دیگر معتبر نیست؛ لطفاً منوی فعلی را باز کنید.")
        raise ApplicationHandlerStop
    text = ALIASES.get(text, text)
    # Make the callback look exactly like a normal text button to the
    # canonical router.  This also lets every existing service handler run.
    original = getattr(update, "message", None)

    class Proxy:
        def __init__(self, message, value):
            self._message = message
            self.text = value
        def __getattr__(self, name):
            return getattr(self._message, name)

    try:
        update.message = Proxy(q.message, text)
        await B.router(update, context)
    except Exception:
        log.exception("universal inline callback failed: %s", text)
        await q.message.reply_text("❌ اجرای این گزینه ناموفق بود. لطفاً دوباره تلاش کنید.")
    finally:
        try:
            update.message = original
        except Exception:
            pass
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_telegram_universal_button_guard", False):
        return
    app.add_handler(
        CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^(ik:|ticket:reply:)",),
        group=-101,
    )
    B._telegram_universal_button_guard = True
    log.info("Telegram universal button guard installed")
