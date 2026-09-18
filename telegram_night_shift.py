"""Legacy night-shift module retained only for compatibility. NetYar is 24/7."""
def is_friday(): return False
def is_open(): return True
def _allowed(B,uid): return True
def install(app,B):
    B._night_shift_installed=True
    return True
