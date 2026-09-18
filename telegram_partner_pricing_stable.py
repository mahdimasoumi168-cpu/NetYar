"""Deterministic per-partner service price adjustment.
Admin selects one partner, then the bot asks for EVERY active service one by one:
increase/decrease/no-change -> amount -> next service.
Changes are stored only for that partner.
"""
import re
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

CANCELS={"❌ انصراف","لغو","انصراف","Cancel","إلغاء"}
ENTRY_CALLBACKS={"adm:partner_price_seq","adm:partner_price_adjust","adm:partner_price_adjust_final"}

def _now(): return datetime.now(timezone.utc).isoformat()
def _digits(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))

def _menu(B):
    try:
        import telegram_canonical_admin_final as C
        return C.menu()
    except Exception:
        try:
            import telegram_admin_plus as A
            return A._admin_menu()
        except Exception:
            return None

def _find_partner(B,text):
    raw=_digits(text).strip()
    raw=raw.replace("+98","0").replace("0098","0")
    conn=B.db.conn
    if raw.isdigit():
        p=conn.execute("SELECT * FROM partners WHERE id=? OR phone=? LIMIT 1",(int(raw),raw)).fetchone()
        if p:return p
    p=conn.execute("SELECT * FROM partners WHERE phone=? LIMIT 1",(raw,)).fetchone()
    if p:return p
    return conn.execute("SELECT * FROM partners WHERE name LIKE ? ORDER BY id LIMIT 1",(f"%{text.strip()}%",)).fetchone()

def _services(B):
    rows=B.db.conn.execute("SELECT key,name,price FROM services WHERE active=1 ORDER BY id").fetchall()
    return [(r["key"],r["name"],int(r["price"] or 0)) for r in rows]

def _current(B,pid,key,public_price):
    r=B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key)).fetchone()
    return int(r["price"]) if r else public_price

def _save(B,pid,key,value):
    if value is None:
        return
    if value==0:
        B.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key))
    else:
        B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices(partner_id,service_key,price,updated_at) VALUES(?,?,?,?)",(pid,key,value,_now()))
    B.db.conn.commit()

def _direction_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزایش قیمت",callback_data="ppdir:up"),InlineKeyboardButton("➖ کاهش قیمت",callback_data="ppdir:down")],
        [InlineKeyboardButton("⏭ بدون تغییر",callback_data="ppdir:skip")],
        [InlineKeyboardButton("❌ انصراف",callback_data="ppcancel")]
    ])

def _clear(st):
    for k in ("sp_partner_id","sp_partner_name","sp_services","sp_index","sp_current","sp_direction","sp_results"):
        st.pop(k,None)
    st["mode"]=None

async def _ask_service(message,B,st):
    services=st.get("sp_services") or []
    idx=int(st.get("sp_index",0))
    if idx>=len(services):
        pid=st.get("sp_partner_id")
        name=st.get("sp_partner_name","-")
        results=st.get("sp_results",[])
        _clear(st)
        summary="\n".join(results) or "هیچ تغییری ثبت نشد."
        await message.reply_text(f"✅ قیمت‌گذاری تک‌تک خدمات برای همکار کامل شد.\n\n👤 همکار: {name}\n\n{summary}",reply_markup=_menu(B))
        return
    key,name,public=services[idx]
    current=_current(B,int(st["sp_partner_id"]),key,public)
    st["sp_current"]=current
    await message.reply_text(
        f"👤 همکار: {st.get('sp_partner_name','-')}\n\n"
        f"🔹 خدمت {idx+1} از {len(services)}: {name}\n"
        f"💰 قیمت فعلی: {current:,} تومان\n\n"
        "نوع تغییر این خدمت را انتخاب کنید:",
        reply_markup=_direction_kb()
    )

async def callback(update,context,B):
    q=update.callback_query
    if not q or not B.admin(q.from_user.id): return
    data=str(q.data or "")
    if data not in ENTRY_CALLBACKS and not data.startswith("ppdir:") and data!="ppcancel": return
    await q.answer()
    uid=q.from_user.id; st=B.S.setdefault(uid,{"admin":True})
    if data in ENTRY_CALLBACKS:
        st.update({"mode":"sp_partner","sp_partner_id":None,"sp_index":0,"sp_results":[]})
        await q.message.reply_text("📈 افزایش/کاهش قیمت همکار خاص\n\n👤 شماره موبایل، شناسه یا نام همکار را وارد کنید:")
        raise ApplicationHandlerStop
    if data=="ppcancel":
        _clear(st)
        await q.message.reply_text("❌ قیمت‌گذاری لغو شد.",reply_markup=_menu(B))
        raise ApplicationHandlerStop
    if not str(st.get("mode","")).startswith("sp_") or not st.get("sp_partner_id"):
        await q.message.reply_text("❌ نشست قیمت‌گذاری منقضی شده است.",reply_markup=_menu(B))
        raise ApplicationHandlerStop
    direction=data.split(":",1)[1]
    st["sp_direction"]=direction
    idx=int(st.get("sp_index",0)); key,name,public=st["sp_services"][idx]
    current=int(st.get("sp_current",0))
    if direction=="skip":
        st.setdefault("sp_results",[]).append(f"⏭ {name}: بدون تغییر ({current:,} تومان)")
        st["sp_index"]=idx+1
        await _ask_service(q.message,B,st)
        raise ApplicationHandlerStop
    st["mode"]="sp_amount"
    await q.message.reply_text(f"🔢 برای «{name}» مبلغ تغییر را به تومان وارد کنید:")
    raise ApplicationHandlerStop

async def text(update,context,B):
    if not update.message or not update.effective_user or not B.admin(update.effective_user.id): return
    uid=update.effective_user.id; st=B.S.setdefault(uid,{})
    mode=st.get("mode"); t=(update.message.text or "").strip()
    if mode not in {"sp_partner","sp_amount"}: return
    if t in CANCELS:
        _clear(st); await update.message.reply_text("❌ قیمت‌گذاری لغو شد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
    if mode=="sp_partner":
        p=_find_partner(B,t)
        if not p:
            await update.message.reply_text("❌ همکار پیدا نشد. شماره موبایل، شناسه یا نام را دوباره وارد کنید.")
            raise ApplicationHandlerStop
        services=_services(B)
        if not services:
            _clear(st); await update.message.reply_text("❌ هیچ خدمت فعالی برای قیمت‌گذاری وجود ندارد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
        st.update({"sp_partner_id":int(p["id"]),"sp_partner_name":p["name"] or p["phone"],"sp_services":services,"sp_index":0,"sp_results":[],"mode":"sp_service"})
        await _ask_service(update.message,B,st)
        raise ApplicationHandlerStop
    raw=re.sub(r"[٬,\s]","",_digits(t))
    if not raw.isdigit():
        await update.message.reply_text("❌ فقط عدد وارد کنید؛ مثال: 50000")
        raise ApplicationHandlerStop
    amount=int(raw)
    if amount<0:
        await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
        raise ApplicationHandlerStop
    idx=int(st.get("sp_index",0)); services=st.get("sp_services") or []
    if idx>=len(services):
        _clear(st); await update.message.reply_text("❌ مرحله قیمت‌گذاری نامعتبر است.",reply_markup=_menu(B)); raise ApplicationHandlerStop
    key,name,public=services[idx]; current=int(st.get("sp_current",0)); direction=st.get("sp_direction")
    new=current+amount if direction=="up" else current-amount
    if new<0:
        await update.message.reply_text(f"❌ قیمت نهایی «{name}» منفی می‌شود. مبلغ کاهش را کمتر وارد کنید.")
        raise ApplicationHandlerStop
    _save(B,int(st["sp_partner_id"]),key,new)
    sign="+" if direction=="up" else "-"
    st.setdefault("sp_results",[]).append(f"{'➕' if direction=='up' else '➖'} {name}: {current:,} → {new:,} تومان ({sign}{amount:,})")
    st["sp_index"]=idx+1
    st["mode"]="sp_service"
    await _ask_service(update.message,B,st)
    raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_stable_partner_pricing_v2",False): return
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
      partner_id INTEGER NOT NULL, service_key TEXT NOT NULL, price INTEGER NOT NULL,
      updated_at TEXT NOT NULL, PRIMARY KEY(partner_id,service_key)
    )""")
    B.db.conn.commit()
    app.add_handler(CallbackQueryHandler(lambda u,c:callback(u,c,B),pattern=r"^(adm:partner_price_seq|adm:partner_price_adjust|adm:partner_price_adjust_final|ppdir:(up|down|skip)|ppcancel)$"),group=-13000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:text(u,c,B)),group=-12999)
    B._stable_partner_pricing_v2=True
