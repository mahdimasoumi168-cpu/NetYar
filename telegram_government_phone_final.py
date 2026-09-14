"""Final, isolated handler for the Government-service phone step.

This module intentionally handles only the active ``govv2_phone`` state.
It runs before the legacy Telegram layers so generic handlers cannot swallow
an entered phone number.
"""
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop, MessageHandler, filters


# Persian + Arabic-Indic digits -> ASCII digits.
_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_PHONE_RE = re.compile(r"09\d{9}")


def _normalize_phone(value: str) -> str:
    value = str(value or "").translate(_DIGITS)
    value = re.sub(r"[\s\-()]+", "", value)
    if value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("0098"):
        value = "0" + value[4:]
    elif value.startswith("98"):
        value = "0" + value[2:]
    return re.sub(r"\D", "", value)


def install(app, B):
    if getattr(B, "_government_phone_final", False):
        return

    cancel = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]]
    )

    async def handle(update, context):
        message = getattr(update, "message", None)
        user = getattr(update, "effective_user", None)
        if not message or not user or not message.text:
            return

        state = B.S.get(user.id)
        if not state or state.get("mode") != "govv2_phone":
            return

        phone = _normalize_phone(message.text)
        if not _PHONE_RE.fullmatch(phone):
            await message.reply_text(
                "❌ شماره موبایل صحیح نیست.\n\n"
                "شماره باید ۱۱ رقم و با ۰۹ شروع شود.\n"
                "مثال: 09123456789",
                reply_markup=cancel,
            )
            raise ApplicationHandlerStop

        state["gov_phone"] = phone
        state["mode"] = "govv2_dob"
        await message.reply_text(
            "🎂 تاریخ تولد مشترک را وارد کنید:",
            reply_markup=cancel,
        )
        raise ApplicationHandlerStop

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle),
        group=-4000000,
    )
    B._government_phone_final = True
