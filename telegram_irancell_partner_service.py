"""Telegram partner-only Irancell SIM service."""
import logging, re, secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.irancell_partner")
PRICE = 980_000
SERVICE_KEY = "irancell_sim_issue"
BTN = "📱 حل مشکل سیم کارت ایرانسل"
PHONE_MODE = "irancell_partner_phone"
PHOTO_MODE = "irancell_partner_document"


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))

def _phone(v):
    s = re.sub(r"[\s\-()]+", "", _digits(v).strip())
    if s.startswith("+98"): s = "0" + s[3:]
    elif s.startswith("0098"): s = "0" + s[4:]
    return s if re.fullmatch(r"09\d{9}", s) else None

def _admin_markup(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"irsim:last:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"irsim:detail:{rid}")],
        [InlineKeyboardButton("✅ تأیید درخواست", callback_data=f"irsim:approve:{rid}"), InlineKeyboardButton("❌ رد درخواست", callback_data=f"irsim:reject:{rid}")],
        [InlineKeyboardButton("🔐 درخواست کد امنیتی", callback_data=f"panel:askcode:{rid}")],
    ])

def _ensure_service(B):
    # Legacy SIM service is permanently removed from the live bot.
    try:
        B.db.conn.execute("UPDATE services SET active=0 WHERE key IN ('irancell_sim_issue','sim','sim2','irancell')")
        B.db.conn.commit()
    except Exception:
        log.exception("Could not disable legacy SIM service")
    return False

def install(app, B):
    if getattr(B, "_irancell_partner_service", False):
        return
    _ensure_service(B)
    B._irancell_partner_service = True
    log.info("Legacy Irancell SIM service is disabled")
