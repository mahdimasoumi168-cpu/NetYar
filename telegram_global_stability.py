"""Stable Telegram UI layer.

Telegram does not expose a public API for arbitrary ReplyKeyboard button
background colors. We therefore use colored-square emoji prefixes for a clear,
consistent visual language while keeping the underlying command labels stable.
"""
from telegram import ReplyKeyboardMarkup


def _lang(B, uid):
    return B.S.get(uid, {}).get("lang", "fa")


def _main(B, uid):
    lang = _lang(B, uid)
    if lang == "en":
        rows = [["🟦 FIDA service", "🟩 Printing"],
                ["🟨 Government access", "🟦 Card renewal tracking"],
                ["🟩 SIM services", "🟨 Screening"],
                ["🟦 Tracking", "🟩 My wallet"],
                ["🟨 Contact us", "🟦 Customer complaint"]]
        if B.admin(uid): rows.append(["🟦 Admin panel"])
        rows += [["❌ Cancel"], ["🟩 Partner panel"]]
        return ReplyKeyboardMarkup(rows, resize_keyboard=True)
    if lang == "ar":
        rows = [["🟦 خدمة فيدا", "🟩 خدمات الطباعة"],
                ["🟨 خدمات الحكومة", "🟦 متابعة تجديد البطاقة"],
                ["🟩 خدمات الشريحة", "🟨 الفحص"],
                ["🟦 المتابعة", "🟩 محفظتي"],
                ["🟨 اتصل بنا", "🟦 شكوى العميل"]]
        if B.admin(uid): rows.append(["🟦 لوحة الإدارة"])
        rows += [["❌ إلغاء"], ["🟩 لوحة الشركاء"]]
        return ReplyKeyboardMarkup(rows, resize_keyboard=True)
    rows = [["🟦 فیدای غیر حضوری", "🟩 خدمات چاپ"],
            ["🟨 حل مشکل ورود اتباع دولت من", "🟦 کد رهگیری تمدید کارت‌ها"],
            ["🟩 خدمات سیم کارت", "🟨 آزمون غربالگری"],
            ["🟦 پیگیری", "🟩 کیف پول من"],
            ["🟨 تماس با ما", "🟦 ثبت شکایت مشتریان"]]
    if B.admin(uid): rows.append(["🟦 پنل مدیریت بات"])
    rows += [[B.CANCEL], ["🟩 پنل همکاران"]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def _partner(B, lang="fa"):
    if lang == "en":
        rows = [["🟦 Top up account", "🟩 Government access issue"],
                ["🟨 Track code", "🟦 History"], ["🟩 Balance"],
                ["✉️ Ticket to management"], ["🚪 Exit panel"], ["❌ Cancel"]]
    elif lang == "ar":
        rows = [["🟦 شحن الحساب", "🟩 حل مشكلة خدمات الحكومة"],
                ["🟨 رمز المتابعة", "🟦 السجل"], ["🟩 الرصيد"],
                ["✉️ إرسال تذكرة إلى الإدارة"], ["🚪 خروج من اللوحة"], ["❌ إلغاء"]]
    else:
        rows = [["🟦 شارژ حساب", "🟩 حل مشکل سامانه دولت من"],
                ["🟨 پیگیری کد", "🟦 سوابق"], ["🟩 موجودی"],
                ["✉️ تیکت به مدیریت"], ["🚪 خروج از پنل"], [B.CANCEL]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def install(B):
    if getattr(B, "_telegram_global_stability_installed", False):
        return
    if not hasattr(B, "_original_main_for_global_stability"):
        B._original_main_for_global_stability = B.main

    B.main = lambda uid: _main(B, uid)
    B.partner_kb = lambda lang="fa": _partner(B, lang)

    original_cancel = B.cancel
    async def cancel(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        status = st.get("status", "foreign")
        lang = st.get("lang", "fa")
        mode = st.get("mode")
        if mode in {"partner_exit_choice", "p_phone", "p_pass"}:
            return await original_cancel(update, context)
        st["mode"] = None
        kb = _main(B, uid) if status != "iranian" else ReplyKeyboardMarkup(
            [["🟦 Tracking", "🟩 Partner panel"], ["❌ Cancel"]] if lang == "en" else
            [["🟦 المتابعة", "🟩 لوحة الشركاء"], ["❌ إلغاء"]] if lang == "ar" else
            [["🟦 پیگیری", "🟩 پنل همکاران"], [B.CANCEL]], resize_keyboard=True)
        msg = "❌ Cancelled." if lang == "en" else "❌ تم الإلغاء." if lang == "ar" else "❌ عملیات لغو شد."
        await update.message.reply_text(msg, reply_markup=kb)

    B.cancel = cancel
    B._telegram_global_stability_installed = True
