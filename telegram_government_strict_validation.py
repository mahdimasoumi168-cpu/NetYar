"""Strict validation guard for government-service identity inputs.

Rejects malformed values before the legacy government input handlers can accept them.
It is deliberately narrow and only consumes active government text states.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _digits(value):
    return str(value or "").translate(_DIGITS).strip()


def _phone(value):
    s = _digits(value)
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s


def _dob(value):
    # Only Persian-calendar style dates accepted by the service: 13xx/xx/xx or 14xx/xx/xx.
    return bool(re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", value))


def install(app, B):
    if getattr(B, "_strict_gov_validation", False):
        return

    async def guard(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not getattr(msg, "text", None):
            return
        st = B.S.setdefault(user.id, {})
        mode = str(st.get("mode") or "")
        text = str(msg.text or "").strip()
        d = _digits(text)

        if mode in {"govv2_dob"}:
            if not _dob(text):
                await msg.reply_text("❌ تاریخ تولد نامعتبر است.\n📅 فقط به شکل ۱۳۵۶/۰۱/۰۱ یا ۱۴۰۱/۰۱/۰۱ وارد کنید.")
                raise ApplicationHandlerStop
            return

        if mode in {"govv2_unique"}:
            if not re.fullmatch(r"9\d{9}", d):
                await msg.reply_text("❌ شناسه یکتا نامعتبر است.\n🆔 باید دقیقاً ۱۰ رقم باشد و با ۹ شروع شود.")
                raise ApplicationHandlerStop
            return

        if mode in {"govv2_special"}:
            if not re.fullmatch(r"1\d{11}", d):
                await msg.reply_text("❌ شناسه اختصاصی نامعتبر است.\n🔖 باید دقیقاً ۱۲ رقم باشد و با ۱ شروع شود.")
                raise ApplicationHandlerStop
            return

        if mode in {"govv2_family", "gov_family"}:
            # Household code is required only for Amayesh and must contain more than 4 digits.
            if st.get("gov_doc_type") not in {"card", "amayesh", "آمایش", "کارت آمایش"}:
                return
            if not re.fullmatch(r"\d{5,}", d):
                await msg.reply_text("❌ کد خانوار نامعتبر است.\n👨‍👩‍👧‍👦 کد خانوار باید عددی و حداقل ۵ رقمی باشد.")
                raise ApplicationHandlerStop
            return

        if mode in {"govv2_postal", "gov_postal"}:
            if not re.fullmatch(r"\d{10}", d):
                await msg.reply_text("❌ کد پستی نامعتبر است.\n📮 کد پستی باید دقیقاً ۱۰ رقم باشد.")
                raise ApplicationHandlerStop
            return

        if mode in {"govv2_phone", "gov_phone", "government_phone", "gov_phone_input"}:
            p = _phone(text)
            if not re.fullmatch(r"09\d{9}", p):
                await msg.reply_text("❌ شماره موبایل نامعتبر است.\n📱 شماره موبایل مشترک باید دقیقاً ۱۱ رقم و با ۰۹ شروع شود.")
                raise ApplicationHandlerStop
            return

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guard), group=-250000)
    B._strict_gov_validation = True
