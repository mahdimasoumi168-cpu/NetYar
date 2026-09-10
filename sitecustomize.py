"""NetYar startup compatibility patch."""
from pathlib import Path

try:
    p = Path(__file__).with_name("bot.py")
    if p.exists():
        s = p.read_text(encoding="utf-8")
        original = s
        s = s.replace("async \n\ndef normalize_phone", "\ndef normalize_phone")
        s = s.replace("\ndef partner(u,c):", "\nasync def partner(u,c):")
        s = s.replace('if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری"):', 'if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت"):' )
        if s != original: p.write_text(s, encoding="utf-8")

    sp = Path(__file__).with_name("server.py")
    if sp.exists():
        s = sp.read_text(encoding="utf-8")
        old = '''    if telegram_app is None:\n        log.error("Telegram webhook called before Telegram application was ready")\n        return {"ok":False,"error":"telegram_not_ready"}'''
        new = '''    if telegram_app is None:\n        log.warning("Telegram webhook received during startup; acknowledging until application is ready")\n        return {"ok":True,"starting":True}'''
        if old in s: sp.write_text(s.replace(old,new), encoding="utf-8")
except Exception:
    pass

try:
    import enhancements
except Exception:
    pass
