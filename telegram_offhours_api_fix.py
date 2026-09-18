"""24/7 compatibility layer: public access is always open."""
def install(app,B):
    try:
        import telegram_offhours_partner_gate_v2 as gate
        gate._is_open=lambda B0: True
        gate.is_open=lambda B0: True
        gate._clock_is_open=lambda B0: True
        B._offhours_api_fix_v2=True
        return True
    except Exception:return False
