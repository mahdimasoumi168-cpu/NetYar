"""Last-mile Telegram stability and navigation owner.

Loaded last so stale input modes cannot hijack top-level buttons.
"""
import logging

log = logging.getLogger("netyar.telegram_universal")
LANG_TEXT = "سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید / Choose your language / اختر اللغة:"


def install():
    import bot as B
    import final_ui_flow_patch as F
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if getattr(B, "_telegram_universal_stability", False):
        return

    original_partner = B.partner
    original_router = B.router
    original_ui = F._ui_callback

    def language_markup():
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang:fa"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang:ar"),
        ]])

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
        ]
        if B.admin(uid):
            rows.append(["🛠 پنل مدیریت بات"])
        rows.append([B.CANCEL, "👥 پنل همکاران"])
        return B.kb(rows)

    async def show_language(message):
        await message.reply_text(LANG_TEXT, reply_markup=language_markup())

    async def restart(update, context):
        B.S[update.effective_user.id] = {}
        return await show_language(update.effective_message)

    async def cancel(update, context):
        uid = update.effective_user.id
        old = B.S.get(uid, {}) or {}
        lang = old.get("lang", "fa")
        status = old.get("status", "foreign")
        pid = old.get("partner_id") if old.get("partner_active", True) else None
        B.S[uid] = {"lang": lang, "status": status}
        if pid:
            B.S[uid].update({"partner_id": pid, "partner_active": True})
            markup = B.partner_kb(lang)
        else:
            markup = canonical_main(uid)
        return await update.effective_message.reply_text(
            "❌ عملیات لغو شد.\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=markup,
        )

    async def partner(update, context):
        uid = update.effective_user.id
        st = B.S.get(uid, {}) or {}
        lang = st.get("lang", "fa")
        # Only a genuine active partner session may open the dashboard.
        if st.get("partner_id") and st.get("partner_active", True):
            return await original_partner(update, context)
        B.S[uid] = {"lang": lang, "status": st.get("status", "foreign"), "mode": "p_phone"}
        return await update.effective_message.reply_text(
            "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره همراه همکار را وارد کنید:",
            reply_markup=B.cancel_kb(lang),
        )

    B.main = canonical_main
    B.cancel = cancel
    B.partner = partner

    async def router(update, context):
        text = (getattr(getattr(update, "message", None), "text", "") or "").strip()
        if text in {B.CANCEL, "❌ لغو", "Cancel", "إلغاء"}:
            return await B.cancel(update, context)
        if text in {"🔄 شروع مجدد", "🔄 شروع دوباره", "شروع مجدد", "Restart", "Start again", "بدء من جديد"}:
            return await restart(update, context)
        if text in {"👥 پنل همکاران", "🔵 👥 پنل همکاران"}:
            return await B.partner(update, context)
        top_level = {
            "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ", "🪪 حل مشکل ورود اتباع دولت من",
            "🎫 کد رهگیری تمدید کارت‌ها", "📱 خدمات سیم کارت", "📝 آزمون غربالگری",
            "🎫 پیگیری", "💰 کیف پول من", "📞 تماس با ما", "📝 ثبت شکایت مشتریان",
            "🛠 پنل مدیریت بات",
        }
        if text in top_level:
            uid = update.effective_user.id
            st = B.S.get(uid, {}) or {}
            B.S[uid] = {k: st[k] for k in ("lang", "status", "partner_id", "partner_active") if k in st}
        return await original_router(update, context)

    B.router = router

    async def ui(update, context):
        q = update.callback_query
        token = str(q.data or "")
        entry = F._UI.get(token)
        if entry:
            _owner, label = entry
            label = str(label).strip()
            if label in {"🔄 شروع مجدد", "🔄 شروع دوباره", "Restart", "Start again", "بدء من جديد"}:
                await q.answer()
                return await restart(update, context)
            if label in {B.CANCEL, "❌ لغو", "Cancel", "إلغاء"}:
                await q.answer()
                fake = F._fixed_fake_update(update, label) if hasattr(F, "_fixed_fake_update") else F._fake_update(update, label)
                return await B.cancel(fake, context)
            if label in {"👥 پنل همکاران", "🔵 👥 پنل همکاران"}:
                await q.answer()
                fake = F._fixed_fake_update(update, label) if hasattr(F, "_fixed_fake_update") else F._fake_update(update, label)
                return await B.partner(fake, context)
        return await original_ui(update, context)

    F._ui_callback = ui
    B._telegram_universal_stability = True
    log.info("LAST Telegram universal stability/navigation layer installed")
