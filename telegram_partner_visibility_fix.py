"""Ensure authorized Telegram partners always see the partner panel after /start.
The authorization is resolved from the persistent partner_telegram_links table,
so it does not depend on volatile in-memory state surviving a restart.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_visibility")


def _resolve(B, uid):
    st = B.S.setdefault(uid, {})
    if st.get("partner_id") and st.get("partner_active", True):
        return True
    try:
        row = B.db.conn.execute(
            "SELECT p.id FROM partners p "
            "JOIN partner_telegram_links l ON l.partner_id=p.id "
            "WHERE l.telegram_user_id=? AND p.active=1 LIMIT 1",
            (str(uid),),
        ).fetchone()
        if row:
            st["partner_id"] = row["id"]
            st["partner_active"] = True
            return True
    except Exception:
        log.exception("persistent partner visibility lookup failed")
    return False


def install(app, B):
    if getattr(B, "_partner_visibility_fix", False):
        return
    old_main = B.main

    def main(uid):
        _resolve(B, uid)
        return old_main(uid)

    B.main = main
    B._partner_visibility_fix = True
