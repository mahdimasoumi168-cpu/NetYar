"""Unified card-to-card invoice helpers.

Variza is intentionally disabled. Customer-facing service payments use the
configured card-to-card destination only; verification remains an explicit
management action after the customer submits proof of payment.
"""
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def _card(B=None):
    value = os.getenv("PAYMENT_CARD", "").strip()
    if not value and B is not None:
        try:
            value = B.db.setting("payment_card", "").strip()
        except Exception:
            value = ""
    return value


def _owner(B=None):
    value = os.getenv("PAYMENT_CARD_OWNER", "").strip()
    if not value and B is not None:
        try:
            value = B.db.setting("payment_card_owner", "").strip()
        except Exception:
            value = ""
    return value


def payment_url(B=None, tracking_code=None, amount=None, title=None):
    """Compatibility shim: there is no online payment URL anymore."""
    return ""


def invoice_text(title, amount, tracking_code=None, B=None):
    card = _card(B)
    owner = _owner(B)
    lines = [
        f"🧾 <b>{title}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 مبلغ قابل پرداخت: <b>{int(amount):,} تومان</b>",
    ]
    if tracking_code:
        lines.append(f"🎫 کد پیگیری: <code>{tracking_code}</code>")
    lines += ["━━━━━━━━━━━━━━━━━━", "💳 روش پرداخت: کارت‌به‌کارت"]
    if card:
        lines.append(f"💳 شماره کارت: <code>{card}</code>")
    else:
        lines.append("💳 شماره کارت در تنظیمات مدیریت ثبت نشده است.")
    if owner:
        lines.append(f"👤 به نام: <b>{owner}</b>")
    lines += [
        "",
        "📸 پس از واریز، تصویر رسید پرداخت را همینجا ارسال کنید.",
        "⚠️ انجام خدمت فقط پس از بررسی و تأیید پرداخت توسط مدیریت انجام می‌شود.",
    ]
    return "\n".join(lines)


def invoice_markup(B=None, tracking_code=None, amount=None, title=None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 ارسال رسید پرداخت", callback_data="invoice:receipt")],
        [InlineKeyboardButton("❌ انصراف", callback_data="invoice:cancel")],
    ])


def create_variza_payment(*args, **kwargs):
    """Compatibility stub: Variza payment creation is permanently disabled."""
    return ""
