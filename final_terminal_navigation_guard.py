"""Final terminal navigation guard for Telegram.

Installed last. It owns navigation seams only; service logic remains in the
existing handlers. Colored-square emoji labels are normalized to canonical
labels so UI changes do not break routing.
"""
from __future__ import annotations
import os, re, logging
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
    "✉️ تیکت به مدیریت", "✉️ ارسال تیکت به مدیریت", "📝 تیکت به مدیریت", "🟦 تیکت به مدیریت", "💬 تیکت به مدیریت",
    "✉️ Ticket to management", "📝 Ticket to management", "🟦 Ticket to management", "✉️ إرسال تذكرة إلى الإدارة",
}
CANCEL_LABELS = {"❌ انصراف", "❌ Cancel", "❌ إلغاء", "لغو", "cancel", "Cancel", "إلغاء"}

ALIASES = {
    # Persian visual labels
    "🟦 فیدای غیر حضوری": "🪪 فیدای غیر حضوری", "🟩 خدمات چاپ": "🖨 خدمات چاپ",
    "🟨 حل مشکل ورود اتباع دولت من": "🪪 حل مشکل ورود اتباع دولت من", "🟦 کد رهگیری تمدید کارت‌ها": "🎫 کد رهگیری تمدید کارت‌ها",
    "🟩 خدمات سیم کارت": "📱 خدمات سیم کارت", "🟨 آزمون غربالگری": "📝 آزمون غربالگری",
    "🟦 پیگیری": "🎫 پیگیری", "🟩 کیف پول من": "💰 کیف پول من", "🟨 تماس با ما": "📞 تماس با ما",
    "🟦 ثبت شکایت مشتریان": "📝 ثبت شکایت مشتریان", "🟦 پنل همکاران": "👥 پنل همکاران",
    "🟦 شارژ حساب": "➕ شارژ حساب", "🟩 حل مشکل سامانه دولت من": "🏛 حل مشکل سامانه دولت من",
    "🟨 پیگیری کد": "🔎 پیگیری کد", "🟦 سوابق": "📋 سوابق", "🟩 موجودی": "💰 موجودی",
    "🟦 تیکت به مدیریت": "✉️ تیکت به مدیریت", "🟩 خروج از پنل": "🚪 خروج از پنل",
    # English visual labels
    "🟦 FIDA service": "🪪 FIDA service", "🟩 Printing": "🖨 Printing", "🟨 Government access": "🏛 Government access",
    "🟦 Card renewal tracking": "🎫 Card renewal tracking", "🟩 SIM services": "📱 SIM services", "🟨 Screening": "📝 Screening",
    "🟦 Tracking": "🎫 Tracking", "🟩 My wallet": "💰 My wallet", "🟨 Contact us": "📞 Contact us",
    "🟦 Customer complaint": "📝 Customer complaint", "🟦 Admin panel": "🛠 Admin panel", "🟩 Partner panel": "👥 Partner panel",
    "🟦 Top up account": "➕ Top up account", "🟩 Government access issue": "🏛 Government access issue",
    "🟨 Track code": "🔎 Track code", "🟦 History": "📋 History", "🟩 Balance": "💰 Balance",
    "✉️ Ticket to management": "✉️ Ticket to management", "🚪 Exit panel": "🚪 Exit panel",
    # Arabic visual labels
    "🟦 خدمة فيدا": "🪪 خدمة فيدا", "🟩 خدمات الطباعة": "🖨 خدمات الطباعة", "🟨 خدمات الحكومة": "🏛 خدمات الحكومة",
    "🟦 متابعة تجديد البطاقة": "🎫 متابعة تجديد البطاقة", "🟩 خدمات الشريحة": "📱 خدمات الشريحة", "🟨 الفحص": "📝 الفحص",
    "🟦 المتابعة": "🎫 المتابعة", "🟩 محفظتي": "💰 محفظتي", "🟨 اتصل بنا": "📞 اتصل بنا",
    "🟦 شكوى العميل": "📝 شكوى العميل", "🟦 لوحة الإدارة": "🛠 لوحة الإدارة", "🟩 لوحة الشركاء": "👥 لوحة الشركاء",
    "🟦 شحن الحساب": "➕ شحن الحساب", "🟩 حل مشكلة خدمات الحكومة": "🏛 حل مشكلة خدمات الحكومة",
    "🟨 رمز المتابعة": "🔎 رمز المتابعة", "🟦 السجل": "📋 السجل", "🟩 الرصيد": "💰 الرصيد",
}


def _admin(B, uid):
    try:
        if B.admin(uid): return True
    except Exception: pass
    try:
        adm = getattr(B, "ADM", set()) or set()
        if str(uid) in {str(x) for x in adm}: return True
    except Exception: pass
    raw = os.getenv("ADMIN_IDS", "")
    return str(uid) in {x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip()}


def _proxy_update(update, text):
    original = update.message
    class _Proxy:
        def __init__(self, original_message, value): self._original, self.text = original_message, value
        def __getattr__(self, name): return getattr(self._original, name)
    update.message = _Proxy(original, text)
    return original


def install(app, B):
    if getattr(B, "_final_terminal_navigation_guard", False): return
    old_router = B.router

    async def handle(update, context):
        message, user = update.effective_message, update.effective_user
        if not message or not user: return
        uid = user.id
        text = str(message.text or "").strip()
        st = B.S.setdefault(uid, {})
        canonical = ALIASES.get(text)
        if canonical: text = canonical

        if text in ADMIN_LABELS and _admin(B, uid):
            st.update(admin=True, mode="admin", admin_mode=None)
            await message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=B.amenu())
            raise ApplicationHandlerStop

        if text in PARTNER_LABELS:
            if not st.get("partner_id") and st.get("mode") not in {"partner", "p_phone", "p_pass"}:
                st["mode"], st["step"] = "p_phone", "partner_phone"
                lang = st.get("lang", "fa")
                prompt = {"fa":"📱 شماره موبایل اختصاصی همکار را وارد کنید:","en":"📱 Enter the partner's registered mobile number:","ar":"📱 أدخل رقم هاتف الشريك المسجل:"}.get(lang)
                await message.reply_text(prompt, reply_markup=B.kb([[B.CANCEL]]))
            else:
                await B.partner(update, context)
            raise ApplicationHandlerStop

        if text in TICKET_LABELS and st.get("partner_id"):
            st["mode"] = "partner_ticket_text"
            await message.reply_text("✉️ متن تیکت خود را ارسال کنید.\n\nبرای لغو، دکمه «انصراف» را بزنید.", reply_markup=B.kb([[B.CANCEL]]))
            raise ApplicationHandlerStop

        if st.get("partner_id") and st.get("mode") == "partner_ticket_text":
            if text in CANCEL_LABELS:
                st["mode"] = "partner"
                await message.reply_text("❌ عملیات لغو شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
                raise ApplicationHandlerStop
            if not text: raise ApplicationHandlerStop
            try:
                payload = ("✉️ تیکت جدید همکار\n\n" f"👤 شناسه همکار: {st.get('partner_id','-')}\n" f"📱 شماره: {st.get('partner_phone') or st.get('phone') or st.get('partner') or '-'}\n\n" f"📝 متن:\n{text}")
                await B.notify_admins(context.application, payload)
                st["mode"] = "partner"
                await message.reply_text("✅ تیکت شما برای مدیریت ارسال شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
            except Exception:
                log.exception("partner ticket forwarding failed")
                await message.reply_text("❌ ارسال تیکت ناموفق بود. دوباره تلاش کنید.", reply_markup=B.kb([[B.CANCEL]]))
            raise ApplicationHandlerStop

        if canonical:
            original = _proxy_update(update, canonical)
            try:
                result = await old_router(update, context)
            finally:
                update.message = original
            if result is not None: raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle), group=-300)
    B._final_terminal_navigation_guard = True
