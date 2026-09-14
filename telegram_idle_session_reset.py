"""Safe Telegram idle tracking without breaking active data-entry flows.

This module tracks inactivity but never injects an error/menu message into a
normal Telegram interaction. A stale public session is cleared silently so a
new menu button can always start a fresh flow.
"""
import os
import time
from telegram.ext import MessageHandler, filters

# Keep sessions usable after normal pauses. The value can still be overridden
# with SESSION_IDLE_SECONDS, but never below 15 minutes.
DEFAULT_IDLE_SECONDS = 30 * 60
MIN_IDLE_SECONDS = 15 * 60

# Active conversational states must NEVER be swallowed by the idle guard.
ACTIVE_MODES = {
    "govv2_phone", "govv2_dob", "govv2_unique", "govv2_special",
    "govv2_family", "govv2_identity_number", "govv2_postal",
    "govv2_photo", "govv2_passport_photo1", "govv2_passport_photo2",
    "govv2_passport_photo3", "invoice_pending",
    "p_phone", "p_pass", "partner_phone", "partner_pass",
    "final_partner_chat", "partner_message", "night_phone", "night_pass",
    "topup_amount", "topup_receipt", "public_tracking",
}


def install(app, B):
    if getattr(B, "_idle_session_reset_installed", False):
        return
    try:
        idle_seconds = max(
            MIN_IDLE_SECONDS,
            int(os.getenv("SESSION_IDLE_SECONDS", str(DEFAULT_IDLE_SECONDS))),
        )
    except Exception:
        idle_seconds = DEFAULT_IDLE_SECONDS

    async def text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not msg.text:
            return

        uid = user.id
        now = time.monotonic()
        st = B.S.setdefault(uid, {})
        previous = st.get("_last_activity")
        st["_last_activity"] = now
        mode = str(st.get("mode") or "")

        # Active service/login/ticket flows are never reset by inactivity.
        if mode in ACTIVE_MODES or mode.startswith("govv2_"):
            return

        if previous is None:
            return
        try:
            stale = (now - float(previous)) >= idle_seconds
        except Exception:
            stale = False
        if not stale:
            return

        # Never destroy an authenticated partner/night-shift session merely
        # because there was a pause. Explicit logout remains the logout path.
        if st.get("partner_id") and st.get("partner_active", True):
            return

        # A stale public session is cleared SILENTLY. Do not send an automatic
        # "operation expired" message: that message used to make the next
        # button press look broken and could conflict with the real router.
        transient_keys = (
            "step", "phone", "gov_phone", "gov_dob", "gov_unique",
            "gov_special", "gov_family_code", "gov_identity_number",
            "gov_postal", "_continuation_guard_active",
            "_continuation_guard_mode",
        )
        for key in transient_keys:
            st.pop(key, None)
        st["mode"] = None

    # Track activity before every conversational router, but never consume
    # active service input. This prevents the classic "no reaction" symptom.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-1000000)
    B._idle_session_reset_installed = True
