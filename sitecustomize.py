"""NetYar startup compatibility patch.
Runs automatically before application imports and repairs known legacy bot.py syntax defects.
"""
from pathlib import Path

try:
    # Repair known legacy bot.py syntax/menu defects before imports.
    p = Path(__file__).with_name("bot.py")
    if p.exists():
        s = p.read_text(encoding="utf-8")
        original = s
        s = s.replace("async \n\ndef normalize_phone", "\ndef normalize_phone")
        s = s.replace("\ndef partner(u,c):", "\nasync def partner(u,c):")
        s = s.replace(
            'if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری"):',
            'if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت"):')
        if s != original:
            p.write_text(s, encoding="utf-8")

    # Prevent Telegram's first webhook call during startup from being treated as
    # an application failure. Railway/Telegram can call the old endpoint while a
    # new container is still initializing. Return HTTP 200 until the app is ready;
    # the webhook is registered again immediately after initialization completes.
    sp = Path(__file__).with_name("server.py")
    if sp.exists():
        s = sp.read_text(encoding="utf-8")
        old = '''    if telegram_app is None:\n        log.error("Telegram webhook called before Telegram application was ready")\n        return {"ok":False,"error":"telegram_not_ready"}'''
        new = '''    if telegram_app is None:\n        # Startup race: Telegram may hit the previous webhook while this\n        # container is initializing. ACK it so Telegram does not enter a retry\n        # storm; the startup task registers the live webhook after readiness.\n        log.warning("Telegram webhook received during startup; acknowledging until application is ready")\n        return {"ok":True,"starting":True}'''
        if old in s:
            sp.write_text(s.replace(old, new), encoding="utf-8")
except Exception:
    # Never prevent the application from starting because of this compatibility helper.
    pass
