"""Robust Telegram partner phone lookup.

Partner phone numbers may have been stored in different but equivalent forms
(+98..., 0098..., Persian digits, spaces/dashes). The Telegram login flow
previously normalized only the input and then required an exact DB match.
This layer normalizes both sides and falls back to scanning active partners.
"""
import re
import logging

log = logging.getLogger("netyar.telegram_partner_login_fix")


def normalize_phone(value):
    s = str(value or "").strip()
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def install():
    import bot as B
    if getattr(B, "_telegram_partner_login_fix_installed", False):
        return

    original_partner = B.db.partner

    def partner_fixed(phone):
        normalized = normalize_phone(phone)
        row = original_partner(normalized)
        if row:
            return row
        if not re.fullmatch(r"09\d{9}", normalized):
            return None
        try:
            rows = B.db.conn.execute(
                "SELECT * FROM partners WHERE active=1 ORDER BY id DESC"
            ).fetchall()
            for candidate in rows:
                if normalize_phone(candidate["phone"]) == normalized:
                    return candidate
        except Exception:
            log.exception("Telegram partner fallback lookup failed")
        return None

    B.db.partner = partner_fixed
    B.db.get_partner = partner_fixed

    # Normalize newly-created partner records too, so future logins are stored
    # consistently without changing existing account credentials.
    original_add_partner = B.db.add_partner

    def add_partner_fixed(phone, password, name):
        normalized = normalize_phone(phone)
        if not normalized:
            raise ValueError("شماره همراه همکار معتبر نیست")
        return original_add_partner(normalized, password, name)

    B.db.add_partner = add_partner_fixed
    B._telegram_partner_login_fix_installed = True
    log.info("Telegram partner phone lookup fix installed")
