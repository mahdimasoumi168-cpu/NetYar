"""Final defensive owner for text information entry.

This layer handles the legacy aliases that can otherwise fall through to a
menu/fallback handler. It is intentionally narrow: it only consumes active
input states and never consumes ordinary menu text.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _digits(v):
    return str(v or "").translate(_DIGITS)


def _phone(v):
    s = _digits(v).strip()
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s if re.fullmatch(r"09\d{9}", s) else None


def install(app, B):
    if getattr(B, "_input_hardening_v3", False):
        return

    async def handler(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not getattr(msg, "text", None):
            return
        st = B.S.setdefault(user.id, {})
        mode = str(st.get("mode") or "")
        text = str(msg.text or "").strip()

        # v2 government flow has a dedicated higher-priority owner.
        if mode.startswith("govv2_"):
            return

        if mode in {"gov_phone", "government_phone", "gov_phone_input", "subscriber_phone", "mobile"}:
            p = _phone(text)
            if not p:
                await msg.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.\n\n📱 لطفاً شماره موبایل مشترک را دوباره وارد کنید:")
            else:
                st["gov_phone"] = p
                st["mode"] = "govv2_dob"
                await msg.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        if mode in {"p_phone", "partner_phone"}:
            p = _phone(text)
            if not p:
                await msg.reply_text("❌ شماره موبایل نامعتبر است.\n\n📱 لطفاً شماره همراه همکار را دوباره وارد کنید:")
            else:
                st["phone"] = p
                st["mode"] = "p_pass"
                await msg.reply_text("🔐 رمز عبور را وارد کنید:")
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-300000)
    B._input_hardening_v3 = True
