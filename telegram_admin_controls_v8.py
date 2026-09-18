"""Canonical admin controls v8: pricing, partner pricing, credit, global open/close.
This layer owns only unique callbacks and the final admin menu; it never catches
generic adm:* callbacks, so feature handlers remain reachable.
"""
import re, logging
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.admin_controls_v8")
CANCEL={"لغو","انصراف","❌ انصراف","Cancel","إلغاء"}

def _now(): return datetime.now(timezone.utc).isoformat()
def _digits(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def _admin(B,uid):
    try:return bool(B.admin(uid))
    except Exception:return False
def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t,callback_data=d) for t,d in r] for r in rows])
def _menu(B):
    try:
        import telegram_canonical_admin_final as C
        return C.menu()
    except Exception:
        return _kb([])

def _services(B):
    return B.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall()

def _ensure_partner_prices(B):
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
        partner_id INTEGER NOT NULL, service_key TEXT NOT NULL, price INTEGER NOT NULL,
        updated_at TEXT NOT NULL, PRIMARY KEY(partner_id,service_key))""")
    B.db.conn.commit()

async def _reply_menu(q,B,text):
    await q.message.reply_text(text,reply_markup=_menu(B))

async def _global_toggle(update,context,B):
    q=update.callback_query
    if not q or q.data!="adm:bot_toggle" or not _admin(B,q.from_user.id): return
    await q.answer()
    old=str(B.db.setting("bot_enabled","1") or "1")=="1"
    new=not old
    B.db.set_setting("bot_enabled","1" if new else "0")
    try:B.db.conn.commit()
    except Exception:pass
    state="🟢 کاملاً باز" if new else "🔴 کاملاً بسته"
    await _reply_menu(q,B,f"🔐 وضعیت کامل ربات\n\nوضعیت فعلی: {state}\n\n"
        + ("همه کاربران می‌توانند خدمات را دریافت کنند." if new else "هیچ کاربر عادی نمی‌تواند وارد خدمات، ثبت درخواست یا ادامه فرایند شود. فقط مدیریت امکان باز کردن ربات را دارد."))
    raise ApplicationHandlerStop

async def _price_start(update,context,B):
    q=update.callback_query
    if not q or q.data not in {"adm:price_seq","adm:partner_price_seq"} or not _admin(B,q.from_user.id): return
    await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
    _ensure_partner_prices(B)
    if q.data=="adm:price_seq":
        rows=_services(B)
        if not rows:
            await _reply_menu(q,B,"❌ هیچ خدمتی ثبت نشده است."); raise ApplicationHandlerStop
        st.update({"v8_mode":"general_service","v8_i":0,"v8_services":[dict(r) for r in rows],"v8_prices":{}})
        r=rows[0]
        await q.message.reply_text(f"📈 تنظیم قیمت خدمات — مرحله ۱ از {len(rows)}\n\n"
            f"خدمت: {r['name']}\nقیمت فعلی: {int(r['price'] or 0):,} تومان\n\n"
            "برای این خدمت انتخاب کنید:",reply_markup=_kb([
                [("➕ افزایش قیمت","v8:action:up"),("➖ کاهش قیمت","v8:action:down")],
                [("⏭ بدون تغییر","v8:action:skip"),("❌ انصراف","v8:cancel")]]))
    else:
        st.update({"v8_mode":"partner_select","v8_i":0,"v8_services":[dict(r) for r in _services(B)],"v8_prices":{}})
        await q.message.reply_text("📈 قیمت اختصاصی همکار\n\nشماره موبایل، شناسه یا نام همکار را وارد کنید:")
    raise ApplicationHandlerStop

async def _v8_cb(update,context,B):
    q=update.callback_query; data=str(q.data or "")
    if not data.startswith("v8:") or not _admin(B,q.from_user.id): return
    await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
    if data=="v8:cancel":
        for k in list(st):
            if k.startswith("v8_"): st.pop(k,None)
        await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
    if data.startswith("v8:action:"):
        action=data.rsplit(":",1)[1]
        mode=st.get("v8_mode")
        if mode not in {"general_service","partner_service"}: return
        if action=="skip":
            await _advance(B,update,context,st,uid,skip=True); raise ApplicationHandlerStop
        st["v8_action"]=action; st["v8_mode"]="general_amount" if mode=="general_service" else "partner_amount"
        svc=st["v8_services"][int(st.get("v8_i",0))]
        await q.message.reply_text(("➕ مبلغ افزایش" if action=="up" else "➖ مبلغ کاهش")+f" برای «{svc['name']}» را به تومان وارد کنید:")
        raise ApplicationHandlerStop

async def _advance(B,update,context,st,uid,skip=False):
    i=int(st.get("v8_i",0)); svc=st["v8_services"][i]
    if not skip:
        raw=re.sub(r"[٬,\s]","",_digits(st.get("v8_pending_amount","0")))
        if not raw.isdigit(): return
        amount=int(raw); action=st.get("v8_action")
        current=int(svc.get("price") or 0) if st.get("v8_mode")=="general_amount" else _partner_current(B,int(st["v8_partner_id"]),svc["key"],int(svc.get("price") or 0))
        new=current+amount if action=="up" else max(0,current-amount)
        if st.get("v8_mode")=="general_amount":
            B.db.set_setting("service_price_"+str(svc["key"]),str(new))
            B.db.conn.execute("UPDATE services SET price=? WHERE key=?",(new,svc["key"]))
        else:
            B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(int(st["v8_partner_id"]),svc["key"],new,_now()))
        B.db.conn.commit(); st.setdefault("v8_prices",{})[svc["key"]]=new
    st["v8_pending_amount"]=None; st["v8_action"]=None; st["v8_i"]=i+1
    if st["v8_i"]>=len(st["v8_services"]):
        who=("همکار" if "v8_partner_id" in st else "خدمات")
        vals=st.get("v8_prices",{})
        summary="\n".join(f"• {x['name']}: {vals.get(x['key'],'بدون تغییر'):,} تومان" if isinstance(vals.get(x['key']),int) else f"• {x['name']}: بدون تغییر" for x in st["v8_services"])
        for k in list(st):
            if k.startswith("v8_"): st.pop(k,None)
        await update.effective_message.reply_text(f"✅ قیمت‌گذاری تک‌تک تمام شد — {who}.\n\n{summary}",reply_markup=_menu(B)); return
    n=st["v8_services"][st["v8_i"]]
    st["v8_mode"]="partner_service" if "v8_partner_id" in st else "general_service"
    await update.effective_message.reply_text(f"مرحله {st['v8_i']+1} از {len(st['v8_services'])}\n\n"
        f"خدمت: {n['name']}\nقیمت فعلی: {int(n.get('price') or 0):,} تومان\n\nانتخاب کنید:",
        reply_markup=_kb([[("➕ افزایش قیمت","v8:action:up"),("➖ کاهش قیمت","v8:action:down")],[("⏭ بدون تغییر","v8:action:skip"),("❌ انصراف","v8:cancel")]]))

def _partner_current(B,pid,key,fallback):
    try:
        r=B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key)).fetchone()
        return int(r["price"]) if r else fallback
    except Exception:return fallback

async def _v8_text(update,context,B):
    m=update.effective_message; u=update.effective_user
    if not m or not u or not _admin(B,u.id): return
    st=B.S.setdefault(u.id,{}); mode=st.get("v8_mode"); t=(m.text or "").strip()
    if not mode:return
    if t in CANCEL:
        for k in list(st):
            if k.startswith("v8_"): st.pop(k,None)
        await m.reply_text("❌ عملیات لغو شد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
    if mode=="partner_select":
        raw=_digits(t); p=None
        if raw.isdigit(): p=B.db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=? LIMIT 1",(int(raw),raw)).fetchone()
        if not p:p=B.db.conn.execute("SELECT * FROM partners WHERE name LIKE ? LIMIT 1",(f"%{t}%",)).fetchone()
        if not p: await m.reply_text("❌ همکار پیدا نشد. دوباره شماره، شناسه یا نام را وارد کنید."); raise ApplicationHandlerStop
        st["v8_partner_id"]=int(p["id"]); st["v8_partner_name"]=p["name"] or p["phone"]; st["v8_mode"]="partner_service"
        if not st.get("v8_services"): st["v8_services"]=[dict(r) for r in _services(B)]
        if not st["v8_services"]: await m.reply_text("❌ هیچ خدمتی ثبت نشده است.",reply_markup=_menu(B)); raise ApplicationHandlerStop
        r=st["v8_services"][0]
        await m.reply_text(f"👤 همکار: {st['v8_partner_name']}\n\nمرحله ۱ از {len(st['v8_services'])}\n"
            f"خدمت: {r['name']}\nقیمت فعلی: {_partner_current(B,int(p['id']),r['key'],int(r['price'] or 0)):,} تومان\n\nانتخاب کنید:",
            reply_markup=_kb([[("➕ افزایش قیمت","v8:action:up"),("➖ کاهش قیمت","v8:action:down")],[("⏭ بدون تغییر","v8:action:skip"),("❌ انصراف","v8:cancel")]]))
        raise ApplicationHandlerStop
    if mode in {"general_amount","partner_amount"}:
        raw=re.sub(r"[٬,\s]","",_digits(t))
        if not raw.isdigit() or int(raw)<=0:
            await m.reply_text("❌ مبلغ معتبر وارد کنید."); raise ApplicationHandlerStop
        st["v8_pending_amount"]=raw
        await _advance(B,update,context,st,u.id,skip=False)
        raise ApplicationHandlerStop

def install(app,B):
    if getattr(B,"_admin_controls_v8",False): return True
    _ensure_partner_prices(B)
    # Never replace the canonical menu owner with a second implementation.
    try:
        import telegram_canonical_admin_final as C
        B.amenu=C.menu
        B.admin_menu_final=C.menu
        import telegram_admin_plus as A
        A._admin_menu=C.menu
    except Exception:
        B.amenu=lambda: _menu(B)
        B.admin_menu_final=lambda: _menu(B)
    app.add_handler(CallbackQueryHandler(lambda u,c:_global_toggle(u,c,B),pattern=r"^adm:bot_toggle$"),group=-60000)
    app.add_handler(CallbackQueryHandler(lambda u,c:_price_start(u,c,B),pattern=r"^adm:(price_seq|partner_price_seq)$"),group=-59999)
    app.add_handler(CallbackQueryHandler(lambda u,c:_v8_cb(u,c,B),pattern=r"^v8:"),group=-59998)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_v8_text(u,c,B)),group=-59997)
    B._admin_controls_v8=True
    log.info("ADMIN CONTROLS V8 ACTIVE")
    return True
