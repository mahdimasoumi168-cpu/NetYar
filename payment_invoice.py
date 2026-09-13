"""Shared service invoices using manual card-to-card payment only.

Variza is intentionally disabled for service invoices. Customer services use
card-to-card payment and are confirmed by management; partner services are
charged from the partner balance.
"""
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

log = __import__("logging").getLogger("netyar.payment")


def _card(B=None):
    card = os.getenv("PAYMENT_CARD", "").strip()
    owner = os.getenv("PAYMENT_CARD_OWNER", "").strip()
    if B is not None:
        try:
            card = card or B.db.setting("card_number", "").strip()
            owner = owner or B.db.setting("card_owner", "").strip()
        except Exception:
            pass
    return card, owner


def _variza_enabled():
    # Deliberately disabled by business policy. Do not read or use Variza
    # credentials even if they remain in Railway variables.
    return False


def create_variza_payment(B, tracking_code, amount, title):
    """Compatibility stub: Variza payment creation is disabled."""
    return ""


def payment_url(B=None, tracking_code=None, amount=None, title=None):
    # No external gateway URL is returned. The invoice is card-to-card.
    return ""


def invoice_text(title, amount, tracking_code=None, B=None):
    card, owner = _card(B)
    lines = [
        f"🧾 <b>{title}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 مبلغ قابل پرداخت: <b>{int(amount):,} تومان</b>",
    ]
    if tracking_code:
        lines.append(f"🎫 کد پیگیری: <code>{tracking_code}</code>")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        "💳 <b>روش پرداخت: کارت به کارت</b>",
        f"💳 شماره کارت: <code>{card or 'شماره کارت در تنظیمات ثبت نشده است'}</code>",
        f"👤 به نام: <b>{owner or '-'}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "📸 پس از واریز، تصویر رسید را ارسال کنید.",
        "⏳ پس از بررسی و تأیید واقعی وجه توسط مدیریت، درخواست انجام می‌شود.",
    ]
    return "\n".join(lines)


def invoice_markup(B=None, tracking_code=None, amount=None, title=None):
    card, _ = _card(B)
    rows = []
    if card:
        try:
            from telegram import CopyTextButton
            rows.append([InlineKeyboardButton("📋 کپی شماره کارت", copy_text=CopyTextButton(text=card))])
        except Exception:
            pass
    rows.append([InlineKeyboardButton("📸 ارسال رسید پرداخت", callback_data="invoice:receipt")])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="invoice:cancel")])
    return InlineKeyboardMarkup(rows)

# Kept only for backward compatibility with imports. It does not register a
# Variza payment route.
