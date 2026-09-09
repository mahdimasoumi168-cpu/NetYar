"""NetYar startup compatibility patch.
Runs automatically before application imports and repairs known legacy bot.py syntax defects.
"""
from pathlib import Path

try:
    p = Path(__file__).with_name("bot.py")
    if p.exists():
        s = p.read_text(encoding="utf-8")
        original = s
        s = s.replace("async \n\ndef normalize_phone", "\ndef normalize_phone")
        s = s.replace("\ndef partner(u,c):", "\nasync def partner(u,c):")
        # Keep screening and follow-up as separate menu actions instead of disabling the combined item.
        s = s.replace(
            'if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری"):',
            'if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت"):'
        )
        if s != original:
            p.write_text(s, encoding="utf-8")
except Exception:
    # Never prevent the application from starting because of this compatibility helper.
    pass
