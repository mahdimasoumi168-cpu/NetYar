"""Final navigation/language/ticket stability layer.

This layer is deliberately installed last.  It fixes the shared seams that were
still being overwritten by legacy compatibility modules:
- partner permanent exit keeps the user's Iranian/foreign area;
- language selection changes the navigation menus and accepts translated labels;
- Telegram partner ticket entry remains available from the partner panel;
- Rubika ticket replies are terminal so legacy wrappers cannot echo/re-route them.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("netyar.final_navigation_language_stability")


def _norm(value: str) -> str:
    return str(value or "").strip()


def _lang(uid, B):
    return B.S.get(uid, {}).get("lang", "fa")


def _iranian_kb(B, uid):
    lang = _lang(uid, B)
    if lang == "en":
        return B.kb([["🎫 Tracking"], ["👥 Partner panel"], [B.CANCEL]])
    if lang == "ar":
        return B.kb([["🎫 المتابعة"], ["👥 لوحة الشركاء"], [B.CANCEL]])
    return B.kb([["🎫 پیگیری"], ["👥 پنل همکاران"], [B.CANCEL]])


def _foreign_text(lang):
    return {
        "fa": "منوی خدمات کمک یار مهاجر 👇",
        "en": "Mohajer Helper services 👇",
        "ar": "خدمات مساعد المهاجر 👇",
    }.get(lang, "منوی خدمات کمک یار مهاجر 👇")


def _citizenship(lang):
    text = {
        "fa": "آیا اتباع هستید یا ایرانی؟",
        "en": "Are you a foreign resident or an Iranian citizen?",
        "ar": "هل أنت من الأجانب أم مواطن إيراني؟",
    }.get(lang, "آیا اتباع هستید یا ایرانی؟")
    labels = {
        "fa": ("🪪 اتباع هستم", "🇮🇷 ایرانی هستم"),
        "en": ("🪪 Foreign resident", "🇮🇷 Iranian citizen"),
        "ar": ("🪪 مقيم أجنبي", "🇮🇷 مواطن إيراني"),
    }.get(lang, ("🪪 اتباع هستم", "🇮🇷 ایرانی هستم"))
    return text, labels


def _install_telegram():
    import bot as B
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if getattr(B, "_final_navigation_language_stability", False):
        return

    # Language callback: do not leave Persian citizenship labels behind.
    async def langcb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        lang = str(q.data or "").split(":", 1)[-1]
        if lang not in {"fa", "en", "ar"}:
            lang = "fa"
        old = dict(B.S.get(uid, {}))
        old["lang"] = lang
        B.S[uid] = old
        text, labels = _citizenship(lang)
        await q.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(labels[0], callback_data="st:foreign"), InlineKeyboardButton(labels[1], callback_data="st:iranian")]
            ]),
        )

    B.langcb = langcb

    # Keep status menus language-aware, including the Iranian path.
    async def statuscb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        status = str(q.data or "").split(":", 1)[-1]
        st = B.S.setdefault(uid, {})
        st["status"] = status
        st.pop("mode", None)
        lang = _lang(uid, B)
        if status == "iranian":
            text = {
                "fa": "🇮🇷 منوی خدمات ایرانی 👇",
                "en": "🇮🇷 Iranian user menu 👇",
                "ar": "🇮🇷 قائمة المستخدم الإيراني 👇",
            }.get(lang, "🇮🇷 منوی خدمات ایرانی 👇")
            return await q.message.reply_text(text, reply_markup=_iranian_kb(B, uid))
        return await q.message.reply_text(_foreign_text(lang), reply_markup=B.main(uid))

    B.statuscb = statuscb

    # Permanent partner exit must return to the same citizenship area.
    async def partner_exit_choice(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = _norm(getattr(update.message, "text", ""))
        if st.get("mode") != "partner_exit_choice":
            return False
        if text in {"⏸ خروج موقت", "⏸ Temporary exit", "⏸ خروج مؤقت"}:
            st["partner_active"] = False
            st["mode"] = None
            return await update.message.reply_text(
                "⏸ خروج موقت انجام شد.",
                reply_markup=_iranian_kb(B, uid) if st.get("status") == "iranian" else B.main(uid),
            )
        if text in {"🔒 خروج دائمی", "🔒 Permanent exit", "🔒 خروج دائم"}:
            status = st.get("status", "foreign")
            lang = st.get("lang", "fa")
            # Preserve only the user's area/language.  Partner credentials and
            # transient modes are intentionally discarded.
            B.S[uid] = {"status": status, "lang": lang}
            if status == "iranian":
                msg = {
                    "fa": "🔒 خروج دائمی انجام شد.\n\n🇮🇷 به منوی ایرانی برگشتید.",
                    "en": "🔒 Permanent exit completed.\n\n🇮🇷 You are back in the Iranian user menu.",
                    "ar": "🔒 تم تسجيل الخروج الدائم.\n\n🇮🇷 عدت إلى قائمة المستخدم الإيراني.",
                }.get(lang, "🔒 خروج دائمی انجام شد.")
                return await update.message.reply_text(msg, reply_markup=_iranian_kb(B, uid))
            msg = {
                "fa": "🔒 خروج دائمی انجام شد.\n\n🪪 به منوی اتباع برگشتید.",
                "en": "🔒 Permanent exit completed.\n\n🪪 You are back in the foreign-resident menu.",
                "ar": "🔒 تم تسجيل الخروج الدائم.\n\n🪪 عدت إلى قائمة المقيمين الأجانب.",
            }.get(lang, "🔒 خروج دائمی انجام شد.")
            return await update.message.reply_text(msg, reply_markup=B.main(uid))
        if text in {B.CANCEL, "❌ Cancel", "❌ إلغاء", "لغو"}:
            st["mode"] = None
            return await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=_iranian_kb(B, uid) if st.get("status") == "iranian" else B.main(uid),
            )
        return await update.message.reply_text(
            "لطفاً یکی از گزینه‌های خروج را انتخاب کنید.",
            reply_markup=B.kb([["⏸ خروج موقت", "🔒 خروج دائمی"], [B.CANCEL]]),
        )

    B.partner_exit_choice = partner_exit_choice

    # Translate navigation labels back to the canonical Persian handlers.
    aliases = {
        "👥 Partner panel": "👥 پنل همکاران",
        "👥 لوحة الشركاء": "👥 پنل همکاران",
        "🔵 👥 Partner panel": "👥 پنل همکاران",
        "🔵 👥 لوحة الشركاء": "👥 پنل همکاران",
        "🎫 Tracking": "🎫 پیگیری",
        "🎫 Follow-up": "🎫 پیگیری",
        "🎫 المتابعة": "🎫 پیگیری",
        "🚪 Exit panel": "🚪 خروج از پنل",
        "🚪 الخروج من اللوحة": "🚪 خروج از پنل",
        "➕ Add balance": "➕ شارژ حساب",
        "💰 My balance": "💰 موجودی",
        "📋 History": "📋 سوابق",
        "🔎 Track code": "🔎 پیگیری کد",
        "✉️ Ticket to management": "✉️ ارسال تیکت به مدیریت",
        "📝 Ticket to management": "✉️ ارسال تیکت به مدیریت",
    }
    old_router = B.router

    async def router(update, context):
        uid = update.effective_user.id
        text = _norm(getattr(update.message, "text", ""))
        mapped = aliases.get(text)
        if mapped:
            update.message.text = mapped
        return await old_router(update, context)

    # Do not replace Message.text (read-only on PTB 20+).  Use a tiny proxy.
    class _Proxy:
        def __init__(self, original, text):
            self._original = original
            self.text = text
        def __getattr__(self, name):
            return getattr(self._original, name)

    async def safe_router(update, context):
        uid = update.effective_user.id
        text = _norm(getattr(update.message, "text", ""))
        mapped = aliases.get(text)
        if not mapped:
            return await old_router(update, context)
        original = update.message
        update.message = _Proxy(original, mapped)
        try:
            return await old_router(update, context)
        finally:
            update.message = original

    B.router = safe_router
    B._final_navigation_language_stability = True


def _install_rubika():
    import rubika_v2 as R

    if getattr(R, "_final_rubika_terminal_ticket_router", False):
        return

    old_handle = R.handle

    def _media(update):
        if not isinstance(update, dict):
            return False
        u = update.get("update") if isinstance(update.get("update"), dict) else update
        m = u.get("message") or u.get("new_message") or {}
        return bool(m.get("file") or m.get("file_id") or any(m.get(k) for k in ("photo", "video", "voice", "audio", "document", "file_inline")))

    def _msgid(update):
        u = update.get("update") if isinstance(update, dict) and isinstance(update.get("update"), dict) else update
        m = u.get("message") or u.get("new_message") or {}
        return str(m.get("message_id") or u.get("message_id") or "")

    def _chat(update, fallback):
        u = update.get("update") if isinstance(update, dict) and isinstance(update.get("update"), dict) else update
        m = u.get("message") or u.get("new_message") or {}
        return str(u.get("chat_id") or m.get("chat_id") or m.get("chat_key") or fallback or "")

    def _forward(source, mid, target):
        if not source or not mid or not target:
            return False
        try:
            R.call("forwardMessage", {"from_chat_id": str(source), "message_id": str(mid), "to_chat_id": str(target), "disable_notification": False})
            return True
        except Exception:
            log.exception("Rubika ticket forward failed")
            return False

    def handle(uid, chat, x, update):
        uid = str(uid)
        x = _norm(x)
        st = R.STATE.setdefault(uid, {})
        step = st.get("step")

        # Once a continuous ticket is active, consume the update here and do
        # not pass it through any older wrapper. This removes duplicate/garbled
        # replies caused by stacked legacy Rubika handlers.
        if step == "partner_ticket_chat":
            if x in {"0", "10", "15", "99", "❌ انصراف", "🔄 شروع مجدد", "cancel", "Cancel"}:
                st["step"] = "partner"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.partner_rows())
                return
            phone = str(st.get("ticket_partner_phone") or st.get("partner") or "").strip()
            target = str(st.get("ticket_admin_chat") or R.db.setting(f"ticket_admin_{phone}", "") or next(iter(R.ADMIN_IDS), "")).strip()
            if not target:
                R.send(chat, "❌ مدیریت برای پاسخ در دسترس نیست.")
                return
            if _media(update):
                if not _forward(chat, _msgid(update), target):
                    R.send(chat, "❌ ارسال رسانه انجام نشد.")
            else:
                R.send(target, f"📨 پیام همکار\n👥 {phone or '-'}\n\n{x or 'پیام بدون متن'}")
            R.db.set_setting(f"ticket_admin_{phone}", str(target))
            R.send(chat, "✅ پیام برای مدیریت ارسال شد.")
            return

        if step == "admin_ticket_chat" and R.is_admin(uid):
            if x in {"15", "99", "🔄 شروع مجدد"}:
                st["step"] = "admin"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.admin_rows())
                return
            target = str(st.get("ticket_partner_chat") or "").strip()
            if not target:
                R.send(chat, "❌ چت همکار پیدا نشد.", R.admin_rows())
                st["step"] = "admin"
                return
            if _media(update):
                if not _forward(chat, _msgid(update), target):
                    R.send(chat, "❌ ارسال رسانه انجام نشد.")
            else:
                R.send(target, f"👔 پیام مدیریت\n\n{x or 'پیام بدون متن'}")
            R.db.set_setting(f"ticket_admin_{str(st.get('ticket_partner_phone') or '')}", str(chat))
            return

        return old_handle(uid, chat, x, update)

    R.handle = handle
    R._final_rubika_terminal_ticket_router = True


def install():
    try:
        _install_telegram()
    except Exception:
        log.exception("Telegram final navigation/language layer failed")
    try:
        _install_rubika()
    except Exception:
        log.exception("Rubika final terminal ticket layer failed")
