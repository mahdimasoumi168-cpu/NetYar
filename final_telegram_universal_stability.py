"""Last-mile Telegram stability and navigation owner.

This module is deliberately loaded last. It normalizes top-level navigation,
prevents stale input modes from hijacking button presses, and gives Restart a
single canonical language-selection screen.
"""
import logging
from types import SimpleNamespace

log = logging.getLogger("netyar.telegram_universal")

LANG_TEXT = "سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید / Choose your language / اختر اللغة:"


def install():
    import bot as B
    import final_ui_flow_patch as F
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if getattr(B, "_telegram_universal_stability", False):
        return

    def language_markup():
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar"),
        ]])

    def clean_state(uid, keep_partner=True):
        old = B.S.get(uid, {}) or {}
        out = {"lang": old.get("lang", "fa")}
        if old.get("status"):
            out["status"] = old["status"]
        if keep_partner and old.get("partner_id"):
            out["partner_id"] = old["partner_id"]
            out["partner_active"] = bool(old.get("partner_active", True))
        B.S[uid] = out
        return out

    def canonical_main(uid):
        st = B.S.get(uid, {}) or {}
        if st.get("partner_id") and st.get("partner_active", True):
            return B.partner_kb(st.get("lang", "fa"))
        rows = [
            ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
            ["🪪 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها"],
            ["📱 خدمات سیم کارت", "📝 آزمون غربالگری"],
            ["🎫 پیگیری", "💰 کیف پول من"],
            ["📞 تماس با ما", "📝 ثبت شکایت مشتریان"],
            [B.CANCEL, "👥 پنل همکاران"],
        ]
        if B.admin(uid):
            rows.insert(-1, ["🛠 پنل مدیریت بات"])
        return B.kb(rows)

    async def show_language(message):
        await message.reply_text(LANG_TEXT, reply_markup=language_markup())

    async def universal_restart(update, context):
        uid = update.effective_user.id
        B.S[uid] = {}
        return await show_language(update.effective_message)

    async def universal_cancel(update, context):
        uid = update.effective_user.id
        st = B.S.get(uid, {}) or {}
        # Cancel always destroys transient input state. A logged-in partner
        # remains in the partner panel; everyone else returns to the canonical menu.
        partner_id = st.get("partner_id") if st.get("partner_active", True) else None
        lang = st.get("lang", "fa")
        status = st.get("status", "foreign")
        B.S[uid] = {"lang": lang, "status": status}
        if partner_id:
            B.S[uid].update({"partner_id": partner_id, "partner_active": True})
            markup = B.partner_kb(lang)
        else:
            markup = canonical_main(uid)
        await update.effective_message.reply_text(
            "❌ عملیات لغو شد.\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=markup,
        )

    async def universal_partner(update, context):
        uid = update.effective_user.id
        st = B.S.get(uid, {}) or {}
        lang = st.get("lang", "fa")
        # If a partner session exists, show its current panel. Otherwise this
        # action is always the beginning of a fresh phone/password login.
        if st.get("partner_id") and st.get("partner_active", True):
            return await B.partner(update, context)
        B.S[uid] = {"lang": lang, "status": st.get("status", "foreign"), "mode": "p_phone"}
        return await update.effective_message.reply_text(
            "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره همراه همکار را وارد کنید:",
            reply_markup=B.cancel_kb(lang),
        )

    # Keep the canonical public functions at the very end of the patch chain.
    B.main = canonical_main
    B.cancel = universal_cancel
    old_partner = B.partner
    async def guarded_partner(update, context):
        uid = update.effective_user.id
        st = B.S.get(uid, {}) or {}
        if st.get("mode") not in (None, "p_phone", "p_pass") and not st.get("partner_id"):
            st = clean_state(uid, keep_partner=False)
        return await universal_partner(update, context)
    B.partner = guarded_partner

    # Old reply-keyboard text messages can still arrive after a restart or
    # from an older Telegram message. Handle navigation labels before the old
    # stateful router sees them.
    old_router = B.router
    async def guarded_router(update, context):
        text = (getattr(getattr(update, "message", None), "text", "") or "").strip()
        uid = update.effective_user.id
        if text in {B.CANCEL, "❌ لغو", "Cancel", "إلغاء"}:
            return await B.cancel(update, context)
        if text in {"🔄 شروع مجدد", "🔄 شروع دوباره", "شروع مجدد", "Restart", "Start again", "بدء من جديد"}:
            return await universal_restart(update, context)
        if text == "👥 پنل همکاران" or text == "🔵 👥 پنل همکاران":
            return await B.partner(update, context)
        # A top-level service button is a new navigation action, not an input
        # for a previous flow. Clear only transient mode, preserving language
        # and partner identity.
        top_level = {
            "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ", "🪪 حل مشکل ورود اتباع دولت من",
            "🎫 کد رهگیری تمدید کارت‌ها", "📱 خدمات سیم کارت", "📝 آزمون غربالگری",
            "🎫 پیگیری", "💰 کیف پول من", "📞 تماس با ما", "📝 ثبت شکایت مشتریان",
            "🛠 پنل مدیریت بات",
        }
        if text in top_level:
            st = B.S.get(uid, {}) or {}
            keep = {k: st[k] for k in ("lang", "status", "partner_id", "partner_active") if k in st}
            B.S[uid] = keep
        return await old_router(update, context)
    B.router = guarded_router

    # Harden inline callbacks. The callback label, not stale process state,
    # decides top-level navigation.
    old_ui = F._ui_callback
    async def universal_ui(update, context):
        q = update.callback_query
        token = str(q.data or "")
        entry = F._UI.get(token)
        if entry:
            _owner, label = entry
            label = str(label).strip()
            if label in {"🔄 شروع مجدد", "🔄 شروع دوباره", "Restart", "Start again", "بدء من جديد"}:
                await q.answer()
                return await universal_restart(update, context)
            if label in {B.CANCEL, "❌ لغو", "Cancel", "إلغاء"}:
                await q.answer()
                fake = F._fixed_fake_update(update, label) if hasattr(F, "_fixed_fake_update") else F._fake_update(update, label)
                return await B.cancel(fake, context)
            if label in {"👥 پنل همکاران", "🔵 👥 پنل همکاران"}:
                await q.answer()
                fake = F._fixed_fake_update(update, label) if hasattr(F, "_fixed_fake_update") else F._fake_update(update, label)
                return await B.partner(fake, context)
        return await old_ui(update, context)
    F._ui_callback = universal_ui

    B._telegram_universal_stability = True
    log.info("LAST Telegram universal stability/navigation layer installed")
