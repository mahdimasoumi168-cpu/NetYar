"""Central admin access policy: administrators are never blocked by business hours."""

def install(app, B):
    if getattr(B, "_admin_access_policy", False):
        return
    old_allowed = getattr(B, "night_allowed", None)
    def admin_allowed(uid):
        try:
            return bool(B.admin(uid))
        except Exception:
            return False
    B.admin_always_allowed = admin_allowed
    B._admin_access_policy = True
