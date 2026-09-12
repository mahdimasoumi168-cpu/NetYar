"""Small final Telegram safety layer.

Keeps citizenship-aware menus stable without replacing the existing service
handlers. Installed after the legacy extensions and before the terminal guard.
"""
from telegram import ReplyKeyboardMarkup


def _lang(B, uid):
    return B.S.get(uid, {}).get("lang", "fa")


def _main(B, uid):
    lang = _lang(B, uid)
    if lang == "en":
        rows = [["🪪 FIDA service", "🖨 Printing"],
                ["🏛 Government access", "🎫 Card renewal tracking"],
                ["📱 SIM services", "📝 Screening"],
                ["🎫 Tracking", "💰 My wallet"],
                ["📞 Contact us", "📝 Customer complaint"]]
        if B.admin(uid): rows.append(["🛠 Admin panel"])
        rows += [["❌ Cancel"], ["👥 Partner panel"]]
    elif lang == "ar":
        rows = [["🪪 خدمة فيدا", "🖨 خدمات الطباعة"],
                ["🏛 خدمات الحكومة", "🎫 متابعة تجديد البطاقة"],
                ["📱 خدمات الشريحة", "📝 الفحص"],
                ["🎫 المتابعة", "💰 محفظتي"],
                ["📞 اتصل بنا", "📝 شكوى العميل"]]
        if B.admin(uid): rows.append(["🛠 لوحة الإدارة"])
        rows += [["❌ إلغاء"], ["👥 لوحة الشركاء"]]
    else:
        return B._original_main_for_global_stability(uid) if hasattr(B, "_original_main_for_global_stability") else B.main(uid)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def _partner(B, lang="fa"):
    if lang == "en":
        rows = [["➕ Add balance", "🏛 Government access"], ["🔎 Track code", "📋 History"],
                ["💰 My balance"], ["✉️ Ticket to management"], ["🚪 Exit panel"], ["❌ Cancel"]]
    elif lang == "ar":
        rows = [["➕ شحن الحساب", "🏛 خدمات الحكومة"], ["🔎 متابعة الرمز", "📋 السجل"],
                ["💰 رصيدي"], ["✉️ إرسال تذكرة إلى الإدارة"], ["🚪 الخروج من اللوحة"], ["❌ إلغاء"]]
    else:
        rows = [["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🔎 پیگیری کد", "📋 سوابق"],
                ["💰 موجودی"], ["✉️ تیکت به مدیریت"], ["🚪 خروج از پنل"], [B.CANCEL]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def install(B):
    if getattr(B, "_telegram_global_stability_installed", False): return
    # Save the current canonical Persian main once; never recursively wrap it.
    if not hasattr(B, "_original_main_for_global_stability"):
        B._original_main_for_global_stability = B.main
    if not hasattr(B, "_original_partner_kb_for_global_stability"):
        B._original_partner_kb_for_global_stability = B.partner_kb

    def main(uid):
        return _main(B, uid)

    def partner_kb(lang="fa"):
        return _partner(B, lang)

    B.main = main
    B.partner_kb = partner_kb

    # Generic Cancel must preserve the user's citizenship area.
    original_cancel = B.cancel
    async def cancel(update, context):
        uid = update.effective_user.id
        st = B.S.get(uid, {})
        # Let active partner/ticket handlers own their own cancel operation.
        if st.get("mode") in {"partner_ticket_text", "partner_exit_choice", "p_phone", "p_pass"}:
            return await original_cancel(update, context)
        st["mode"] = None
        status = st.get("status", "foreign")
        lang = st.get("lang", "fa")
        if status == "iranian":
            kb = ReplyKeyboardMarkup(
                [["🎫 Tracking", "👥 Partner panel"], ["❌ Cancel"]] if lang == "en" else
                [["🎫 المتابعة", "👥 لوحة الشركاء"], ["❌ إلغاء"]] if lang == "ar" else
                [["🎫 پیگیری", "👥 پنل همکاران"], [B.CANCEL]], resize_keyboard=True)
        else:
            kb = B.main(uid)
        await update.message.reply_text("❌ Cancelled." if lang == "en" else "❌ تم الإلغاء." if lang == "ar" else "❌ عملیات لغو شد.", reply_markup=kb)
    B.cancel = cancel
    B._telegram_global_stability_installed = True
