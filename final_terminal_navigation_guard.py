"""Terminal navigation guard for both Telegram and Rubika.

Installed last. It owns only the ambiguous seams where legacy routers were
swallowing partner/admin buttons or letting a handled message fall through.
"""
from __future__ import annotations
import os
import re
import logging
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.final_terminal_navigation_guard")

ADMIN_LABELS = {
    "🛠 پنل مدیریت بات", "🔵 🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت",
    "🛠 Admin panel", "🛠 لوحة الإدارة",
}
PARTNER_LABELS = {
    "👥 پنل همکاران", "🔵 👥 پنل همکاران", "👥 Partner panel", "🔵 👥 Partner panel",
    "👥 لوحة الشركاء", "🔵 👥 لوحة الشركاء",
}
TICKET_LABELS = {
    "✉️ تیکت به مدیریت", "✉️ ارسال تیکت به مدیریت", "📝 تیکت به مدیریت",
    "✉️ Ticket to management", "📝 Ticket to management",
    "✉️ إرسال تذكرة إلى الإدارة",
}
CANCEL_LABELS = {"❌ انصراف", "❌ Cancel", "❌ إلغاء", "لغو", "cancel", "Cancel", "إلغاء"}


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


def _lang_menu(B, uid):
    lang = B.S.get(uid, {}).get("lang", "fa")
    if lang == "en":
        return B.kb([["🎫 Tracking"], ["👥 Partner panel"], ["❌ Cancel"]])
    if lang == "ar":
        return B.kb([["🎫 المتابعة"], ["👥 لوحة الشركاء"], ["❌ إلغاء"]])
    return B.kb([["🎫 پیگیری"], ["👥 پنل همکاران"], [B.CANCEL]])


def install(app, B):
    if getattr(B, "_final_terminal_navigation_guard", False):
        return

    async def handle(update, context):
        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return
        uid = user.id
        text = str(message.text or "").strip()
        st = B.S.setdefault(uid, {})

        # 1) Admin panel is terminal and must win over every legacy router.
        if text in ADMIN_LABELS and _admin(B, uid):
            st["admin"] = True
            st["mode"] = "admin"
            st["admin_mode"] = None
            await message.reply_text(
                "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
                reply_markup=B.amenu(),
            )
            raise ApplicationHandlerStop

        # 2) Partner panel must be reachable even while status=iranian.
        if text in PARTNER_LABELS:
            if not st.get("partner_id") and st.get("mode") not in {"partner", "p_phone", "p_pass"}:
                # Let the canonical partner-login handler ask for phone.
                st["mode"] = "p_phone"
                st["step"] = "partner_phone"
                lang = st.get("lang", "fa")
                prompt = {
                    "fa": "📱 شماره موبایل اختصاصی همکار را وارد کنید:",
                    "en": "📱 Enter the partner's registered mobile number:",
                    "ar": "📱 أدخل رقم هاتف الشريك المسجل:",
                }.get(lang)
                await message.reply_text(prompt, reply_markup=B.kb([[B.CANCEL]]))
            else:
                await B.partner(update, context)
            raise ApplicationHandlerStop

        # 3) Partner ticket entry. Do not let the Iranian-menu guard reject it.
        if text in TICKET_LABELS and st.get("partner_id"):
            st["mode"] = "partner_ticket_text"
            await message.reply_text(
                "✉️ متن تیکت خود را ارسال کنید.\n\nبرای لغو، دکمه «انصراف» را بزنید.",
                reply_markup=B.kb([[B.CANCEL]]),
            )
            raise ApplicationHandlerStop

        # 4) While partner ticket is open, consume text here and never fall through.
        if st.get("partner_id") and st.get("mode") == "partner_ticket_text":
            if text in CANCEL_LABELS:
                st["mode"] = "partner"
                await message.reply_text("❌ عملیات لغو شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
                raise ApplicationHandlerStop
            if not text:
                return
            try:
                payload = (
                    "✉️ تیکت جدید همکار\n\n"
                    f"👤 شناسه همکار: {st.get('partner_id', '-') }\n"
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

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle), group=-300)
    B._final_terminal_navigation_guard = True
