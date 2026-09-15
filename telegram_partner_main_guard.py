"""Keep an authenticated partner inside the partner panel.

Legacy service layers sometimes call B.main(uid) on an error, missing route,
or cancellation. For an active partner session that must never expose the
public/customer main menu. This guard transparently redirects those internal
B.main() calls back to the partner keyboard while preserving normal public
behavior after logout.
"""
import logging

log = logging.getLogger("netyar.telegram.partner_main_guard")


def install(app, B):
    if getattr(B, "_partner_main_guard", False):
        return

    original_main = getattr(B, "main", None)
    if not callable(original_main):
        log.warning("B.main is not callable; partner main guard skipped")
        return

    def guarded_main(uid):
        try:
            st = B.S.setdefault(uid, {})
            active = bool(
                st.get("partner_id")
                and st.get("partner_active", False)
                and not st.get("partner_logged_out", False)
                and st.get("mode") not in {"p_phone", "p_password", "night_phone", "night_password"}
            )
            partner_kb = getattr(B, "partner_kb", None)
            if active and callable(partner_kb):
                return partner_kb(st.get("lang", "fa"))
        except Exception:
            log.exception("partner main guard failed; using original main")
        return original_main(uid)

    B.main = guarded_main
    B._partner_main_guard = True
