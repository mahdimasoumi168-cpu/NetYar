"""Final navigation/language/ticket stability layer.

Owns navigation seams only: citizenship-aware cancellation and partner exit,
language-aware menus, Telegram partner ticket entry, and terminal Rubika ticket
routing. Service business logic remains in the existing handlers.
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
    return {"fa": "منوی خدمات کمک یار مهاجر 👇", "en": "Mohajer Helper services 👇", "ar": "خدمات مساعد المهاجر 👇"}.get(lang, "منوی خدمات کمک یار مهاجر 👇")


def _citizenship(lang):
    text = {"fa": "آیا اتباع هستید یا ایرانی؟", "en": "Are you a foreign resident or an Iranian citizen?", "ar": "هل أنت من الأجانب أم مواطن إيراني؟"}.get(lang, "آیا اتباع هستید یا ایرانی؟")
    labels = {"fa": ("🪪 اتباع هستم", "🇮🇷 ایرانی هستم"), "en": ("🪪 Foreign resident", "🇮🇷 Iranian citizen"), "ar": ("🪪 مقيم أجنبي", "🇮🇷 مواطن إيراني")}.get(lang, ("🪪 اتباع هستم", "🇮🇷 ایرانی هستم"))
    return text, labels


def _install_telegram():
    import bot as B
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    if getattr(B, "_final_navigation_language_stability", False):
        return

    async def langcb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        lang = str(q.data or "").split(":", 1)[-1]
        if lang not in {"fa", "en", "ar"}: lang = "fa"
        old = dict(B.S.get(uid, {})); old["lang"] = lang; B.S[uid] = old
        text, labels = _citizenship(lang)
        await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(labels[0], callback_data="st:foreign"), InlineKeyboardButton(labels[1], callback_data="st:iranian")]]))

    B.langcb = langcb

    async def statuscb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        status = str(q.data or "").split(":", 1)[-1]
        st = B.S.setdefault(uid, {}); st["status"] = status; st.pop("mode", None)
        lang = _lang(uid, B)
        if status == "iranian":
            text = {"fa": "🇮🇷 منوی خدمات ایرانی 👇", "en": "🇮🇷 Iranian user menu 👇", "ar": "🇮🇷 قائمة المستخدم الإيراني 👇"}.get(lang, "🇮🇷 منوی خدمات ایرانی 👇")
            return await q.message.reply_text(text, reply_markup=_iranian_kb(B, uid))
        return await q.message.reply_text(_foreign_text(lang), reply_markup=B.main(uid))

    B.statuscb = statuscb

    # Critical: the legacy cancel() hard-coded status=foreign.  When an
    # Iranian user cancels the partner phone/password flow, that is wrong.
    old_cancel = B.cancel
    if not getattr(B, "_final_citizenship_cancel", False):
        async def citizenship_cancel(update, context):
            uid = update.effective_user.id
            st = B.S.get(uid, {})
            lang = st.get("lang", "fa")
            status = st.get("status")
            mode = st.get("mode")
            if status == "iranian" and mode in {"p_phone", "p_pass", "partner_phone", "partner_pass"}:
                B.S[uid] = {"status": "iranian", "lang": lang}
                text = {"fa": "❌ عملیات لغو شد.\n\n🇮🇷 به منوی ایرانی برگشتید.", "en": "❌ Operation cancelled.\n\n🇮🇷 Back to the Iranian menu.", "ar": "❌ تم إلغاء العملية.\n\n🇮🇷 عدت إلى قائمة المستخدم الإيراني."}.get(lang, "❌ عملیات لغو شد.")
                return await update.effective_message.reply_text(text, reply_markup=_iranian_kb(B, uid))
            return await old_cancel(update, context)
        B.cancel = citizenship_cancel
        B._final_citizenship_cancel = True

    async def partner_exit_choice(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        text = _norm(getattr(update.message, "text", ""))
        if st.get("mode") != "partner_exit_choice": return False
        if text in {"⏸ خروج موقت", "⏸ Temporary exit", "⏸ خروج مؤقت"}:
            st["partner_active"] = False; st["mode"] = None
            return await update.message.reply_text("⏸ خروج موقت انجام شد.", reply_markup=_iranian_kb(B, uid) if st.get("status") == "iranian" else B.main(uid))
        if text in {"🔒 خروج دائمی", "🔒 Permanent exit", "🔒 خروج دائم"}:
            status = st.get("status", "foreign"); lang = st.get("lang", "fa")
            B.S[uid] = {"status": status, "lang": lang}
            if status == "iranian":
                msg = {"fa": "🔒 خروج دائمی انجام شد.\n\n🇮🇷 به منوی ایرانی برگشتید.", "en": "🔒 Permanent exit completed.\n\n🇮🇷 You are back in the Iranian user menu.", "ar": "🔒 تم تسجيل الخروج الدائم.\n\n🇮🇷 عدت إلى قائمة المستخدم الإيراني."}.get(lang, "🔒 خروج دائمی انجام شد.")
                return await update.message.reply_text(msg, reply_markup=_iranian_kb(B, uid))
            msg = {"fa": "🔒 خروج دائمی انجام شد.\n\n🪪 به منوی اتباع برگشتید.", "en": "🔒 Permanent exit completed.\n\n🪪 You are back in the foreign-resident menu.", "ar": "🔒 تم تسجيل الخروج الدائم.\n\n🪪 عدت إلى قائمة المقيمين الأجانب."}.get(lang, "🔒 خروج دائمی انجام شد.")
            return await update.message.reply_text(msg, reply_markup=B.main(uid))
        if text in {B.CANCEL, "❌ Cancel", "❌ إلغاء", "لغو"}:
            st["mode"] = None
            return await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=_iranian_kb(B, uid) if st.get("status") == "iranian" else B.main(uid))
        return await update.message.reply_text("لطفاً یکی از گزینه‌های خروج را انتخاب کنید.", reply_markup=B.kb([["⏸ خروج موقت", "🔒 خروج دائمی"], [B.CANCEL]]))

    B.partner_exit_choice = partner_exit_choice

    aliases = {
        "👥 Partner panel": "👥 پنل همکاران", "👥 لوحة الشركاء": "👥 پنل همکاران", "🔵 👥 Partner panel": "👥 پنل همکاران", "🔵 👥 لوحة الشركاء": "👥 پنل همکاران",
        "🎫 Tracking": "🎫 پیگیری", "🎫 Follow-up": "🎫 پیگیری", "🎫 المتابعة": "🎫 پیگیری",
        "🚪 Exit panel": "🚪 خروج از پنل", "🚪 الخروج من اللوحة": "🚪 خروج از پنل",
        "➕ Add balance": "➕ شارژ حساب", "💰 My balance": "💰 موجودی", "📋 History": "📋 سوابق", "🔎 Track code": "🔎 پیگیری کد",
        "✉️ Ticket to management": "✉️ ارسال تیکت به مدیریت", "📝 Ticket to management": "✉️ ارسال تیکت به مدیریت",
    }
    old_router = B.router

    class _Proxy:
        def __init__(self, original, text): self._original = original; self.text = text
        def __getattr__(self, name): return getattr(self._original, name)

    async def safe_router(update, context):
        text = _norm(getattr(update.message, "text", ""))
        mapped = aliases.get(text)
        if not mapped: return await old_router(update, context)
        original = update.message; update.message = _Proxy(original, mapped)
        try: return await old_router(update, context)
        finally: update.message = original

    B.router = safe_router
    B._final_navigation_language_stability = True


def _install_rubika():
    import rubika_v2 as R
    if getattr(R, "_final_rubika_terminal_ticket_router", False): return
    old_handle = R.handle

    def _media(update):
        if not isinstance(update, dict): return False
        u = update.get("update") if isinstance(update.get("update"), dict) else update; m = u.get("message") or u.get("new_message") or {}
        return bool(m.get("file") or m.get("file_id") or any(m.get(k) for k in ("photo", "video", "voice", "audio", "document", "file_inline")))
    def _msgid(update):
        u = update.get("update") if isinstance(update, dict) and isinstance(update.get("update"), dict) else update; m = u.get("message") or u.get("new_message") or {}
        return str(m.get("message_id") or u.get("message_id") or "")
    def _chat(update, fallback):
        u = update.get("update") if isinstance(update, dict) and isinstance(update.get("update"), dict) else update; m = u.get("message") or u.get("new_message") or {}
        return str(u.get("chat_id") or m.get("chat_id") or m.get("chat_key") or fallback or "")
    def _forward(source, mid, target):
        if not source or not mid or not target: return False
        try: R.call("forwardMessage", {"from_chat_id": str(source), "message_id": str(mid), "to_chat_id": str(target), "disable_notification": False}); return True
        except Exception: log.exception("Rubika ticket forward failed"); return False
    def handle(uid, chat, x, update):
        uid = str(uid); x = _norm(x); st = R.STATE.setdefault(uid, {}); step = st.get("step")
        if step == "partner_ticket_chat":
            if x in {"0", "10", "15", "99", "❌ انصراف", "🔄 شروع مجدد", "cancel", "Cancel"}:
                st["step"] = "partner"; R.send(chat, "✅ گفت‌وگو بسته شد.", R.partner_rows()); return
            phone = str(st.get("ticket_partner_phone") or st.get("partner") or "").strip(); target = str(st.get("ticket_admin_chat") or R.db.setting(f"ticket_admin_{phone}", "") or next(iter(R.ADMIN_IDS), "")).strip()
            if not target: R.send(chat, "❌ مدیریت برای پاسخ در دسترس نیست."); return
            if _media(update):
                if not _forward(chat, _msgid(update), target): R.send(chat, "❌ ارسال فایل به مدیریت ناموفق بود.")
                return
            try: _forward(chat, _msgid(update), target)
            except Exception: pass
            R.send(chat, "✅ پیام شما برای مدیریت ارسال شد.")
            return
        if step == "ticket_admin_reply":
            if x in {"0", "10", "15", "99", "❌ انصراف", "cancel", "Cancel"}:
                st["step"] = "admin"; R.send(chat, "✅ پاسخ بسته شد.", R.admin_rows()); return
            target = str(st.get("ticket_partner_chat") or "").strip()
            if target:
                if _media(update): _forward(chat, _msgid(update), target)
                else: _forward(chat, _msgid(update), target)
                R.send(chat, "✅ پاسخ برای همکار ارسال شد.")
            return
        return old_handle(uid, chat, x, update)
    R.handle = handle
    R._final_rubika_terminal_ticket_router = True


def install():
    _install_telegram()
    _install_rubika()
