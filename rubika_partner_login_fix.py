"""Minimal Rubika partner-login compatibility patch.

Keeps the existing Rubika state machine intact while making partner phone
lookup tolerant of Persian/Arabic digits and common phone formatting.
"""
import re
import logging

log = logging.getLogger("netyar.rubika_partner_login_fix")


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
    import rubika_v2 as rb
    if getattr(rb, "_netyar_partner_login_fix", False):
        return

    original_get_partner = rb.db.get_partner

    def get_partner_fixed(phone):
        normalized = normalize_phone(phone)
        partner = original_get_partner(normalized)
        if partner:
            return partner
        try:
            rows = rb.db.conn.execute("SELECT * FROM partners WHERE active=1").fetchall()
            for row in rows:
                if normalize_phone(row["phone"]) == normalized:
                    return row
        except Exception:
            log.exception("Rubika partner fallback lookup failed")
        return None

    rb.db.get_partner = get_partner_fixed

    original_check = rb.check_password

    def check_password_fixed(stored_or_plain, plain_or_stored):
        a = str(stored_or_plain or "").strip()
        b = str(plain_or_stored or "").strip()
        try:
            return bool(original_check(a, b)) or bool(original_check(b, a))
        except Exception:
            return False

    rb.check_password = check_password_fixed
    rb._netyar_partner_login_fix = True
    log.info("Rubika partner login compatibility patch installed")
