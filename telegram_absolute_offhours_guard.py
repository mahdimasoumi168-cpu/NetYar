"""Legacy off-hours guard disabled: NetYar is permanently open 24/7."""
def is_open(B): return True
def night_worker(B,uid): return False
def _partner_login_mode(B,uid): return False
def closed_text(B): return "❌ این پیام قدیمی است؛ ربات ۲۴ ساعته فعال است."
def markup(): return None
def install(app,B):
    B._absolute_offhours_guard_v3=True
    return True
