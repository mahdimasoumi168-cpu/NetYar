"""Canonical Telegram access gate: 24/7 operation.
Time-based restrictions and night-shift access controls are intentionally disabled.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

TZ=ZoneInfo("Asia/Tehran")
DEFAULT_OPEN="00:00"; DEFAULT_CLOSE="23:59"
PREFIX="night_worker:"; NIGHT_KEY="night_shift_enabled"; NIGHT_PUBLIC_KEY="night_public_open"
IRANCELL="📱 حل مشکل سیم کارت ایرانسل"

def normalize_phone(value):
    s=str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
    s=re.sub(r"[\s\-()]+","",s)
    if s.startswith("+98"): s="0"+s[3:]
    elif s.startswith("0098"): s="0"+s[4:]
    return s

def _setting(B,key,default):
    try:return str(B.db.setting(key,default) or default)
    except Exception:return default

def night_shift_enabled(B): return True
def night_public_open(B): return True
def _clock_is_open(B): return True
def _is_open(B): return True
def night_access_open(B,uid): return True

def enforce_24x7(B):
    """Single source of truth: Telegram is never blocked by clock/night settings."""
    B._netyar_24x7 = True
    for name in (
        "telegram_business_hours_guard",
        "telegram_night_shift_v2",
        "telegram_night_shift",
        "telegram_final_control",
        "telegram_persian_offhours_lock",
        "telegram_absolute_offhours_guard",
        "telegram_offhours_absolute_start_guard",
        "telegram_night_shift_consistency",
    ):
        try:
            m = __import__(name)
            for fn in ("is_open", "open_now", "_is_open", "_clock_is_open", "closed"):
                if hasattr(m, fn):
                    setattr(m, fn, (lambda *a, **k: True) if fn != "closed" else (lambda *a, **k: ""))
            if hasattr(m, "allowed"):
                m.allowed = lambda *a, **k: True
        except Exception:
            continue
    return True

def _partner_by_phone(B,phone):
    phone=normalize_phone(phone)
    try:
        rows=B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
        for row in rows:
            if normalize_phone(row["phone"])==phone:return row
    except Exception:return None
    return None

def _active_partner_session(B,uid):
    st=B.S.get(uid,{}) or {}
    if st.get("partner_logged_out"): return None
    pid=st.get("partner_id")
    if not pid or st.get("partner_active") is not True:return None
    try:return B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1",(int(pid),)).fetchone()
    except Exception:return None

def is_night_worker(B,uid):
    row=_active_partner_session(B,uid)
    if row:
        try:return str(B.db.setting(PREFIX+str(row["id"]),"0"))=="1"
        except Exception:return False
    return False

def _allowed_during_closed(B,uid): return True
def _closed_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 شروع مجدد",callback_data="off:restart")],[InlineKeyboardButton("👥 پنل همکاران",callback_data="off:partner")]])
def _closed_text(B):
    return "❌ این پیام قدیمی است؛ ربات به‌صورت ۲۴ ساعته فعال است."

def _night_partner_markup(B,uid):
    try:
        import telegram_ui_policy_v2 as UI
        return UI.inline([["➕ شارژ حساب",IRANCELL],["🏛 حل مشکل سامانه دولت من","🎫 درخواست‌های من"],["📱 خدمات سیم کارت","🪪 فیدای غیر حضوری"],["🔎 پیگیری کد","📋 سوابق"],["💰 موجودی"],["🎫 تیکت به مدیریت","💬 ارتباط با مدیریت"],["🚪 خروج از پنل"],["❌ انصراف"]],B,uid)
    except Exception:return B.partner_kb("fa")

def install(app,B):
    if getattr(B,"_offhours_partner_gate_v10",False): return True
    # Explicitly neutralize all legacy time gates.
    B._netyar_24x7=True
    old_main=getattr(B,"main",None)
    if callable(old_main) and not getattr(B,"_night_main_guard_v2",False):
        def always_open_main(uid,*args,**kwargs): return old_main(uid,*args,**kwargs)
        B.main=always_open_main; B._night_main_guard_v2=True
    B._offhours_partner_gate_v10=True
    return True
