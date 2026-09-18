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
    # Canonical switch: 1 = outside-hours access is open, 0 = closed.
    return _setting(B,NIGHT_KEY,"1")=="1"

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
    try:
        if B.admin(uid): return True
    except Exception: pass
    if _clock_is_open(B): return True
    return _public_night_open(B) or is_night_worker(B,uid)

def _allowed_during_closed(B,uid): return night_access_open(B,uid)

def _closed_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 شروع مجدد",callback_data="off:restart")],[InlineKeyboardButton("👥 پنل همکاران",callback_data="off:partner")]])

def _closed_text(B):
    return "❌ ربات در حال حاضر خارج از ساعت کاری بسته است.\n\n⏰ ساعت کاری: ۰۷:۰۰ تا ۱۹:۰۰\n🌙 در صورت فعال بودن دسترسی شبانه، خدمات ادامه دارد."

def enforce_24x7(B):
    # Backward-compatible name: install the canonical gate instead of forcing 24/7.
    B._netyar_24x7=False
    B._netyar_night_gate_authoritative=True
    return True

def install(app,B):
    if getattr(B,"_offhours_partner_gate_v11",False): return True
    B._netyar_24x7=False
    B._netyar_night_gate_authoritative=True
    B._offhours_partner_gate_v11=True
    return True
