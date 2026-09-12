"""Shared service-invoice helpers.

Service completion no longer charges partner balance when this helper is used.
The payment URL can be overridden with SERVICE_PAYMENT_URL on Railway.
"""
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DEFAULT_PAYMENT_URL = "https://variza.ir/pay/SUUWM6uJzf7BKFzQspaT2"


def payment_url(B=None):
    value = os.getenv("SERVICE_PAYMENT_URL", "").strip()
    if not value and B is not None:
        try:
            value = B.db.setting("service_payment_url", "").strip()
        except Exception:
            value = ""
    return value or DEFAULT_PAYMENT_URL


def invoice_text(title, amount, tracking_code=None):
    lines = [
        f"🧾 <b>{title}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 مبلغ قابل پرداخت: <b>{int(amount):,} تومان</b>",
    ]
    if tracking_code:
        lines.append(f"🎫 کد پیگیری: <code>{tracking_code}</code>")
    lines += [
        "━━━━━━━━━━━━━━━━━━",
        "📌 برای پرداخت روی دکمه زیر بزنید.",
        "⏳ پس از پرداخت، رسید/وضعیت پرداخت توسط مدیریت بررسی می‌شود.",
    ]
    return "\n".join(lines)


def invoice_markup(B=None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 پرداخت فاکتور", url=payment_url(B))],
        [InlineKeyboardButton("❌ انصراف", callback_data="invoice:cancel")],
    ])
