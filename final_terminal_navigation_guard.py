"""Final terminal navigation guard for Telegram.

This layer is intentionally last and only owns navigation seams. Business
service handlers remain untouched; common labels are normalized here so old
routers cannot swallow valid buttons.
"""
from __future__ import annotations
import os
import re
import logging
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.final_terminal_navigation_guard")

ADMIN_LABELS = {
    "🛠 پنل مدیریت بات", "🔵 🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت",
    "🟦 پنل مدیریت", "🟦 پنل مدیریت بات", "🔧 پنل مدیریت", "⚙️ پنل مدیریت",
    "🛠 Admin panel", "🛠 لوحة الإدارة", "🟦 Admin panel", "🟦 لوحة الإدارة",
}
PARTNER_LABELS = {
    "👥 پنل همکاران", "🔵 👥 پنل همکاران", "🟦 پنل همکاران",
    "👥 Partner panel", "🔵 👥 Partner panel", "🟦 Partner panel",
    "👥 لوحة الشركاء", "🔵 👥 لوحة الشركاء", "🟦 لوحة الشركاء",
}
TICKET_LABELS = {
    "✉️ تیکت به مدیریت", "✉️ ارسال تیکت به مدیریت", "📝 تیکت به مدیریت",
    "🟦 تیکت به مدیریت", "💬 تیکت به مدیریت",
    "✉️ Ticket to management", "📝 Ticket to management", "🟦 Ticket to management",
    "✉️ إرسال تذكرة إلى الإدارة",
}
CANCEL_LABELS = {"❌ انصراف", "❌ Cancel", "❌ إلغاء", "لغو", "cancel", "Cancel", "إلغاء"}

# Common visual aliases are converted to the canonical labels used by the
# existing service router. This prevents menu redesigns from breaking logic.
ALIASES = {
    "🟦 فیدای غیر حضوری": "🪪 فیدای غیر حضوری",
    "🟩 خدمات چاپ": "🖨 خدمات چاپ",
    "🟨 حل مشکل ورود اتباع دولت من": "🪪 حل مشکل ورود اتباع دولت من",
    "🟦 کد رهگیری تمدید کارت‌ها": "🎫 کد رهگیری تمدید کارت‌ها",
    "🟩 خدمات سیم کارت": "📱 خدمات سیم کارت",
    "🟨 آزمون غربالگری": "📝 آزمون غربالگری",
    "🟦 پیگیری": "🎫 پیگیری",
    "🟩 کیف پول من": "💰 کیف پول من",
    "🟦 تماس با ما": "📞 تماس با ما",
    "🟩 ثبت شکایت مشتریان": "📝 ثبت شکایت مشتریان",
    "🟦 پنل همکاران": "👥 پنل همکاران",
    "🟦 شارژ حساب": "➕ شارژ حساب",
    "🟩 حل مشکل سامانه دولت من": "🏛 حل مشکل سامانه دولت من",
    "🟨 پیگیری کد": "🔎 پیگیری کد",
    "🟦 سوابق": "📋 سوابق",
    "🟩 موجودی": "💰 موجودی",
    "🟦 تیکت به مدیریت": "✉️ تیکت به مدیریت",
    "🟩 خروج از پنل": "🚪 خروج از پنل",
}


def _admin(B, uid):
    try:
        if B.admin(uid):
            return True
    except Exception:
        pass
    try:
        adm = getattr(B, "ADM", set()) or set()
        if str(uid) in {str(x) for x in adm}:
            return True
    except Exception:
        pass
    raw = os.getenv("ADMIN_IDS", "")
    return str(uid) in {x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip()}


def _proxy_update(update, text):
    original = update.message
    class _Proxy:
        def __init__(self, original_message, value):
            self._original = original_message
            self.text = value
        def __getattr__(self, name):
            return getattr(self._original, name)
    update.message = _Proxy(original, text)
    return original


def install(app, B):
    if getattr(B, "_final_terminal_navigation_guard", False):
        return

    old_router = B.router

    async def handle(update, context):
        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return
        uid = user.id
        text = str(message.text or "").strip()
        st = B.S.setdefault(uid, {})

        # Normalize redesigned/color-square labels before anything else.
        canonical = ALIASES.get(text)
        if canonical:
            text = canonical

        # Admin entry is always terminal. This bypasses every legacy service
        # router and uses the current centralized admin menu.
        if text in ADMIN_LABELS and _admin(B, uid):
            st["admin"] = True
            st["mode"] = "admin"
            st["admin_mode"] = None
            await message.reply_text(
                "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
                reply_markup=B.amenu(),
            )
            raise ApplicationHandlerStop

        # Partner entry is also terminal so it can never be interpreted as an
        # Iranian-menu option.
        if text in PARTNER_LABELS:
            if not st.get("partner_id") and st.get("mode") not in {"partner", "p_phone", "p_pass"}:
                st["mode"] = "p_phone"
                st["step"] = "partner_phone"
                lang = st.get("lang", "fa")
                prompt = {
                    "fa": "📱 شماره موبایل اختصاصی همکار را وارد کنید:",
                    "en": "📱 Enter the partner's registered mobile number:",
                    "ar": "📱 أدخل رقم هاتف الشريك المسجل:",
                }.get(lang, "📱 شماره موبایل اختصاصی همکار را وارد کنید:")
                await message.reply_text(prompt, reply_markup=B.kb([[B.CANCEL]]))
            else:
                await B.partner(update, context)
            raise ApplicationHandlerStop

        # Partner ticket entry must win over the Iranian-menu fallback.
        if text in TICKET_LABELS and st.get("partner_id"):
            st["mode"] = "partner_ticket_text"
            await message.reply_text(
                "✉️ متن تیکت خود را ارسال کنید.\n\nبرای لغو، دکمه «انصراف» را بزنید.",
                reply_markup=B.kb([[B.CANCEL]]),
            )
            raise ApplicationHandlerStop

        # Active partner ticket consumes its own text and stops propagation.
        if st.get("partner_id") and st.get("mode") == "partner_ticket_text":
            if text in CANCEL_LABELS:
                st["mode"] = "partner"
                await message.reply_text("❌ عملیات لغو شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
                raise ApplicationHandlerStop
            if not text:
                raise ApplicationHandlerStop
            try:
                payload = (
                    "✉️ تیکت جدید همکار\n\n"
                    f"👤 شناسه همکار: {st.get('partner_id', '-')}\n"
                    f"📱 شماره: {st.get('partner_phone') or st.get('phone') or st.get('partner') or '-'}\n\n"
                    f"📝 متن:\n{text}"
                )
                await B.notify_admins(context.application, payload)
                st["mode"] = "partner"
                await message.reply_text("✅ تیکت شما برای مدیریت ارسال شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            except Exception:
                log.exception("partner ticket forwarding failed")
                await message.reply_text("❌ ارسال تیکت ناموفق بود. دوباره تلاش کنید.", reply_markup=B.kb([[B.CANCEL]]))
            raise ApplicationHandlerStop

        # All other messages go through the canonical router. For aliases we
        # use a proxy because PTB Message.text is read-only.
        if canonical:
            original = _proxy_update(update, canonical)
            try:
                result = await old_router(update, context)
            finally:
                update.message = original
            if result is not None:
                raise ApplicationHandlerStop
            return

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle), group=-300)
    B._final_terminal_navigation_guard = True
