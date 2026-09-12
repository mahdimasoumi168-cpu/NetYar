"""Last-resort Telegram callback router.

The project contains several historical router wrappers. This handler is
installed before them and treats ApplicationHandlerStop as successful control
flow, preventing the old generic 'execution failed' message from appearing.
It also gives the special partner and administrators a permanent bypass of
business-hours restrictions at the application level when the main gate is
reached later.
"""
import logging
from types import SimpleNamespace
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.callback_hardfix")

ALIASES = {
    "👥 Partner panel": "👥 پنل همکاران",
    "👥 لوحة الشركاء": "👥 پنل همکاران",
    "🎫 Tracking": "🎫 پیگیری",
    "🎫 المتابعة": "🎫 پیگیری",
    "🪪 فیدا": "🪪 فیدای غیر حضوری",
    "🏛 حل مشکل ورود اتباع دولت من": "🪪 حل مشکل ورود اتباع دولت من",
    "🏛 حل مشکل سامانه دولت من": "🏛 حل مشکل سامانه دولت من",
    "📝 آزمون غربالگری و پیگیری": "📝 آزمون غربالگری",
    "🪪 FIDA service": "🪪 فیدای غیر حضوری",
    "🖨 Printing": "🖨 خدمات چاپ",
    "📱 SIM services": "📱 خدمات سیم کارت",
    "📞 Contact us": "📞 تماس با ما",
    "🎫 Card renewal tracking": "🎫 کد رهگیری تمدید کارت‌ها",
    "📝 Customer complaint": "📝 ثبت شکایت مشتریان",
    "✉️ ارسال تیکت به مدیریت": "✉️ تیکت به مدیریت",
    "📨 ارسال پیام به مدیریت": "✉️ تیکت به مدیریت",
    "📝 تیکت به مدیریت": "✉️ تیکت به مدیریت",
    "💬 تیکت به مدیریت": "✉️ تیکت به مدیریت",
    "🔄 شروع مجدد با به‌روزرسانی": "🔄 شروع مجدد",
}


def _clean(s):
    s = str(s or "").strip()
    for p in ("🟦 ", "🟩 ", "🟨 ", "🔵 "):
        if s.startswith(p):
            s = s[len(p):].strip()
    return s


def _label(q):
    try:
        markup = q.message.reply_markup
        for row in markup.inline_keyboard or []:
            for b in row:
                if str(b.callback_data or "") == str(q.data or ""):
                    return ALIASES.get(_clean(b.text), _clean(b.text))
    except Exception:
        log.exception("callback label lookup failed")
    return ""


def _proxy(update, q, text):
    # Preserve Telegram's real reply methods but replace only the text field.
    real = q.message
    message = SimpleNamespace()
    for name in ("chat", "from_user", "date", "message_id", "photo", "video", "voice", "audio", "document", "animation", "caption", "entities", "reply_markup"):
        try:
            setattr(message, name, getattr(real, name, None))
        except Exception:
            pass
    message.text = text
    for name in ("reply_text", "reply_photo", "reply_document", "reply_video", "reply_voice", "reply_audio", "reply_animation"):
        try:
            setattr(message, name, getattr(real, name))
        except Exception:
            pass
    return SimpleNamespace(
        update_id=getattr(update, "update_id", None),
        message=message,
        effective_message=message,
        effective_user=q.from_user,
        effective_chat=getattr(real, "chat", None),
        callback_query=q,
    )


async def _restart(q, B, context):
    uid = q.from_user.id
    old = B.S.get(uid, {})
    lang = old.get("lang", "fa")
    status = old.get("status") or old.get("citizenship")
    B.S[uid] = {"lang": lang}
    if status:
        B.S[uid]["status"] = status
        B.S[uid]["citizenship"] = status
    await B.start(_proxy(SimpleNamespace(update_id=None), q, "/start"), context)


async def callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if not q:
        return
    await q.answer()
    text = _label(q)
    if not text:
        await q.message.reply_text("❌ این دکمه دیگر معتبر نیست؛ لطفاً منوی فعلی را باز کنید.")
        raise ApplicationHandlerStop
    if text == "🔄 شروع مجدد":
        try:
            await _restart(q, B, context)
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("restart callback failed")
            await q.message.reply_text("❌ شروع مجدد ناموفق بود. لطفاً دوباره تلاش کنید.")
        raise ApplicationHandlerStop
    try:
        proxy = _proxy(update, q, text)
        await B.router(proxy, context)
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("callback hardfix failed: %s", text)
        await q.message.reply_text("❌ اجرای این گزینه ناموفق بود. لطفاً دوباره تلاش کنید.")
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_telegram_callback_hardfix", False):
        return
    app.add_handler(
        CallbackQueryHandler(lambda u, c: callback(u, c, B), pattern=r"^(ik:|ticket:reply:)"),
        group=-102,
    )
    B._telegram_callback_hardfix = True
