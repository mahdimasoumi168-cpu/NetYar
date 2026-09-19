"""Canonical Telegram access gate: business hours + persistent night/public controls."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

TZ=ZoneInfo("Asia/Tehran")
OPEN=time(7,0); CLOSE=time(19,0)
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

def _public_night_open(B):
    # One authoritative public-night switch. Keep the historical key as a
    # fallback, and tolerate either key being present after upgrades.
    if hasattr(B,"_netyar_night_public_open"):
        return bool(B._netyar_night_public_open)
    value=_setting(B,NIGHT_PUBLIC_KEY,"")
    if value not in {"0","1"}:
        value=_setting(B,NIGHT_KEY,"1")
    return value=="1"

def _clock_is_open(B):
    now=datetime.now(TZ).time()
    return OPEN <= now < CLOSE

def night_shift_enabled(B): return _public_night_open(B)
def night_public_open(B): return _public_night_open(B)
def _is_open(B): return _clock_is_open(B) or _public_night_open(B)

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
        try:return _setting(B,PREFIX+str(row["id"]),"0")=="1"
        except Exception:return False
    return False

def night_access_open(B,uid):
    # Admins are never blocked. During 07:00–19:00 everyone is open. Outside
    # those hours the public-night switch is authoritative; enabled night
    # workers are a separate allow-list and do not depend on stale session state.
    try:
        if B.admin(uid): return True
    except Exception: pass
    if _clock_is_open(B): return True
    if _public_night_open(B): return True
    try:
        row=B.db.conn.execute("SELECT id FROM partners WHERE phone=(SELECT phone FROM partners WHERE id=?)",(B.S.get(uid,{}).get("partner_id"),)).fetchone() if B.S.get(uid,{}).get("partner_id") else None
        if row and _setting(B,PREFIX+str(row["id"]),"0")=="1": return True
    except Exception: pass
    return is_night_worker(B,uid)

def _allowed_during_closed(B,uid): return night_access_open(B,uid)

def _closed_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 شروع مجدد",callback_data="off:restart")],[InlineKeyboardButton("👥 پنل همکاران",callback_data="off:partner")]])

def _closed_text(B):
    return "❌ ربات در حال حاضر خارج از ساعت کاری بسته است.\n\n⏰ ساعت کاری: ۰۷:۰۰ تا ۱۹:۰۰\n🌙 در صورت فعال بودن دسترسی شبانه، خدمات ادامه دارد."

def enforce_24x7(B):
    # Backward-compatible entry point. Rebind legacy gates to this single source
    # of truth so no older module can silently reopen/close the bot.
    B._netyar_24x7=False
    B._netyar_night_gate_authoritative=True
    def _open(*args, **kwargs):
        uid=kwargs.get("uid")
        if uid is None and len(args)>1: uid=args[1]
        if uid is None and args and isinstance(args[0], int): uid=args[0]
        return _is_open(B) if uid is None else night_access_open(B, uid)
    def _allowed(*args, **kwargs):
        uid=kwargs.get("uid")
        if uid is None and len(args)>1: uid=args[1]
        return True if uid is None else night_access_open(B, uid)
    def _closed(*args, **kwargs): return not _is_open(B)
    def _clock(*args, **kwargs): return _clock_is_open(B)
    for name in (
        "telegram_business_hours_guard","telegram_night_shift_v2",
        "telegram_night_shift","telegram_final_control",
        "telegram_persian_offhours_lock","telegram_absolute_offhours_guard",
        "telegram_offhours_absolute_start_guard","telegram_night_shift_consistency",
        "telegram_partner_code_reliable","telegram_management_stability_final",
    ):
        try:
            m=__import__(name)
            for fn in ("is_open","open_now","_is_open"):
                if hasattr(m,fn): setattr(m,fn,_open)
            if hasattr(m,"_clock_is_open"): m._clock_is_open=_clock
            if hasattr(m,"closed"): m.closed=_closed
            if hasattr(m,"allowed"): m.allowed=_allowed
        except Exception:
            continue
    return True

def install(app,B):
    if getattr(B,"_offhours_partner_gate_v11",False): return True
    B._netyar_24x7=False
    B._netyar_night_gate_authoritative=True
    B._offhours_partner_gate_v11=True
    return True
