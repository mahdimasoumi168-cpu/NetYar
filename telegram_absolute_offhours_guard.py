"""Absolute off-hours guard with a safe partner-login exception.

Ordinary users remain blocked outside 07:00-19:00. The partner authentication
conversation is allowed to continue so a whitelisted night worker can prove
identity; service access still requires the night-worker check.
"""
from datetime import datetime,time
from zoneinfo import ZoneInfo
from telegram.ext import MessageHandler,CallbackQueryHandler,ApplicationHandlerStop,filters
from telegram import InlineKeyboardMarkup,InlineKeyboardButton

TZ=ZoneInfo("Asia/Tehran"); DEFAULT_OPEN="07:00"; DEFAULT_CLOSE="19:00"

def _setting(B,key,default):
    try:return str(B.db.setting(key,default) or default)
    except Exception:return default

def is_open(B):
    try:
        o=time.fromisoformat(_setting(B,"work_open",DEFAULT_OPEN)); c=time.fromisoformat(_setting(B,"work_close",DEFAULT_CLOSE)); now=datetime.now(TZ).time()
        return o<=now<c if o<c else (now>=o or now<c)
    except Exception:return False

def night_worker(B,uid):
    try:
        st=B.S.get(uid,{}) or {}
        pid=st.get("partner_id")
        if not pid or st.get("partner_logged_out"): return False
        row=B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1",(int(pid),)).fetchone()
        return bool(row and str(B.db.setting("night_worker:"+str(row["id"]),"0"))=="1")
    except Exception:return False

def _partner_login_mode(B,uid):
    try:
        mode=str((B.S.get(uid,{}) or {}).get("mode") or "")
        return mode in {"partner_entry_phone","partner_entry_pass","p_phone","p_pass","partner_phone","partner_pass","partner_new_wait","partner_reg_pass","partner_reg_name"}
    except Exception:return False

def closed_text(B):
    return ("⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            f"🕖 ساعت کاری: {_setting(B,'work_open',DEFAULT_OPEN)} تا {_setting(B,'work_close',DEFAULT_CLOSE)} به وقت تهران\n\n"
            "🚫 در این زمان خدمات عمومی فعال نیست.\n"
            "🌙 فقط همکاران شب‌کار مجاز می‌توانند وارد پنل شوند.")

def markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 شروع مجدد",callback_data="off:restart")],
                                 [InlineKeyboardButton("👥 پنل همکاران",callback_data="off:partner")]])

def install(app,B):
    if getattr(B,"_absolute_offhours_guard_v2",False): return
    async def gate(update,context):
        if is_open(B): return
        uid=getattr(getattr(update,"effective_user",None),"id",None)
        if uid is None or B.admin(uid) or night_worker(B,uid): return
        msg=getattr(update,"effective_message",None)
        if not msg: return
        if _partner_login_mode(B,uid): return
        txt=str(getattr(msg,"text","") or "").strip()
        if txt in {"🔄 شروع مجدد","شروع مجدد","/restart"}: return
        await msg.reply_text(closed_text(B),reply_markup=markup()); raise ApplicationHandlerStop
    async def callback_gate(update,context):
        if is_open(B): return
        q=getattr(update,"callback_query",None)
        if not q:return
        uid=q.from_user.id
        if B.admin(uid) or night_worker(B,uid):return
        data=str(q.data or "")
        if data in {"off:restart","off:partner"}:return
        if data.startswith("partnerreg:"): return
        if data.startswith("ui2:"):
            try:
                row=B.db.conn.execute("SELECT label,user_id FROM ui2_callbacks WHERE token=?",(data[4:],)).fetchone()
                if row and str(row["user_id"])==str(uid) and str(row["label"]).strip() in {"🔄 شروع مجدد","شروع مجدد","👥 پنل همکاران","👥 Partner panel","👥 لوحة الشركاء"}: return
            except Exception:pass
        try:await q.answer("⏰ خارج از ساعت کاری است.",show_alert=True)
        except Exception:pass
        await q.message.reply_text(closed_text(B),reply_markup=markup()); raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(callback_gate),group=-19999999)
    app.add_handler(MessageHandler(filters.ALL,gate),group=-19999998)
    B._absolute_offhours_guard_v2=True
    return True
