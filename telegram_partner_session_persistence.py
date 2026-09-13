"""Persistent partner-session and management-destination guard.

An authenticated active partner must not be logged out merely because the
normal business-hours gate runs again after inactivity. The partner's Telegram
chat is also the authoritative destination for management communication.
"""
import logging
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.partner_session_persistence")


def _active_partner(B, uid):
    st = B.S.setdefault(uid, {})
    if st.get("partner_logged_out"):
        return None
    pid = st.get("partner_id")
    if not pid:
        return None
    try:
        row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
        if row:
            st["partner_active"] = True
            st["partner_phone"] = row["phone"]
            st["partner"] = row["phone"]
            try:
                B.db.set_setting(f"partner_chat_{pid}", str(uid))
                if row["phone"]:
                    B.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
            except Exception:
                pass
            return row
    except Exception:
        log.exception("partner session resolution failed")
    return None


def install(app, B):
    if getattr(B, "_partner_session_persistence", False):
        return True

    # Refresh an authenticated session before the older business-hours layers
    # get a chance to classify it as an anonymous user.
    async def text_probe(update, context):
        user = getattr(update, "effective_user", None)
        if not user:
            return
        _active_partner(B, user.id)

    async def callback_probe(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        _active_partner(B, q.from_user.id)

    app.add_handler(MessageHandler(filters.ALL, text_probe), group=-69999)
    app.add_handler(CallbackQueryHandler(callback_probe), group=-69998)
    B._partner_session_persistence = True
    B.partner_session_active = lambda uid: bool(_active_partner(B, uid))
    return True
