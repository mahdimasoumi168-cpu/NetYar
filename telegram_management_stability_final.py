"""Management compatibility layer. Working-hours settings are disabled because NetYar is 24/7."""
def _is_open(B): return True
def install(app,B):
    B._management_stability_final=True
    return
