"""Authoritative Telegram admin access guard.

Keeps administrator authorization independent from transient conversation state
and prevents later UI layers from accidentally replacing the real admin check.
"""
from __future__ import annotations
import os, re, logging

log = logging.getLogger("netyar.telegram.admin_access_final_v1")


def _ids():
    vals=set()
    for key in ("ADMIN_IDS", "ADMIN_ID_1", "ADMIN_ID_2", "TELEGRAM_ADMIN_IDS"):
        raw=os.getenv(key, "")
        vals.update(x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip())
    return vals


def install(app, B):
    if getattr(B, "_admin_access_final_v1", False):
        return
    env_ids=_ids()
    B.ADM=set(getattr(B, "ADM", set()) or set()) | env_ids
    old_admin=getattr(B, "admin", None)

    def admin(uid):
        sid=str(uid)
        if sid in B.ADM or sid in env_ids:
            return True
        try:
            st=B.S.get(uid,{}) or {}
            if st.get("admin") is True:
                return True
        except Exception:
            pass
        try:
            row=B.db.conn.execute(
                "SELECT 1 FROM admins WHERE platform='telegram' AND external_id=? AND active=1 LIMIT 1",
                (sid,),
            ).fetchone()
            return bool(row)
        except Exception:
            return False

    B.admin=admin

    # Keep admin identity when /start or another layer rebuilds the session.
    old_start=getattr(B, "start", None)
    if callable(old_start) and not getattr(B, "_admin_start_preserved_v1", False):
        async def start(update, context):
            uid=update.effective_user.id
            is_admin=admin(uid)
            result=await old_start(update, context)
            if is_admin:
                try:
                    B.S.setdefault(uid,{})["admin"]=True
                except Exception:
                    pass
            return result
        B.start=start
        B._admin_start_preserved_v1=True

    B._admin_access_final_v1=True
    log.info("Authoritative Telegram admin access guard installed; env_admins=%d", len(env_ids))
