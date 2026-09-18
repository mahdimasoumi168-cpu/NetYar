"""Canonical global service-price sequence.
Admin chooses price adjustment, then each active service is handled one by one.
"""
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

CANCELS={"❌ انصراف","لغو","انصراف"}
def _digits(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def _menu(B):
    try:
        import telegram_canonical_admin_final as C; return C.menu()
    except Exception:
        return None
def _clear(st):
    for k in ("gsp_index","gsp_direction","gsp_services","gsp_current"): st.pop(k,None)
    st["mode"]=None
def _dirs():
    return InlineKeyboardMarkup([[InlineKeyboardButton("➕ افزایش قیمت",callback_data="gsp:up"),InlineKeyboardButton("➖ کاهش قیمت",callback_data="gsp:down")],[InlineKeyboardButton("⏭ بدون تغییر",callback_data="gsp:skip")],[InlineKeyboardButton("❌ انصراف",callback_data="gsp:cancel")]])
async def _ask(m,B,st):
    services=st.get("gsp_services") or []; i=int(st.get("gsp_index",0))
    if i>=len(services):
        _clear(st); await m.reply_text("✅ قیمت‌گذاری تک‌تک خدمات به پایان رسید.",reply_markup=_menu(B)); return
    key,name,price=services[i]; st["gsp_current"]=price
    await m.reply_text(f"🔹 خدمت {i+1} از {len(services)}\n\n🛎 {name}\n💰 قیمت فعلی: {price:,} تومان\n\nافزایش، کاهش یا بدون تغییر را انتخاب کنید:",reply_markup=_dirs())
async def cb(update,context,B):
    q=update.callback_query
    if not q or not B.admin(q.from_user.id): return
    d=str(q.data or "")
    if d=="adm:price_seq":
        await q.answer(); st=B.S.setdefault(q.from_user.id,{"admin":True})
        rows=B.db.conn.execute("SELECT key,name,price FROM services WHERE active=1 ORDER BY id").fetchall()
        st.update({"mode":"gsp_direction","gsp_index":0,"gsp_services":[(r["key"],r["name"],int(r["price"] or 0)) for r in rows]})
        if not rows: _clear(st); await q.message.reply_text("❌ هیچ خدمت فعالی وجود ندارد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
        await _ask(q.message,B,st); raise ApplicationHandlerStop
    if d=="gsp:cancel":
        _clear(B.S.setdefault(q.from_user.id,{})); await q.answer(); await q.message.reply_text("❌ قیمت‌گذاری لغو شد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
    if d not in {"gsp:up","gsp:down","gsp:skip"}: return
    st=B.S.setdefault(q.from_user.id,{})
    if st.get("mode") not in {"gsp_direction","gsp_amount"} or not st.get("gsp_services"):
        await q.answer("نشست منقضی شده است.",show_alert=True); raise ApplicationHandlerStop
    await q.answer(); i=int(st["gsp_index"]); key,name,price=st["gsp_services"][i]
    if d=="gsp:skip":
        st["gsp_index"]=i+1; await _ask(q.message,B,st); raise ApplicationHandlerStop
    st["gsp_direction"]=d.split(":",1)[1]; st["mode"]="gsp_amount"
    await q.message.reply_text(f"🔢 مبلغ {('افزایش' if st['gsp_direction']=='up' else 'کاهش')} برای «{name}» را به تومان وارد کنید:")
    raise ApplicationHandlerStop
async def txt(update,context,B):
    m=update.message; u=update.effective_user
    if not m or not u or not B.admin(u.id): return
    st=B.S.setdefault(u.id,{})
    if st.get("mode")!="gsp_amount": return
    t=(m.text or "").strip()
    if t in CANCELS:
        _clear(st); await m.reply_text("❌ قیمت‌گذاری لغو شد.",reply_markup=_menu(B)); raise ApplicationHandlerStop
    raw=re.sub(r"[٬,\s]","",_digits(t))
    if not raw.isdigit() or int(raw)<=0:
        await m.reply_text("❌ فقط مبلغ مثبت وارد کنید."); raise ApplicationHandlerStop
    i=int(st["gsp_index"]); key,name,old=st["gsp_services"][i]; amount=int(raw)
    new=old+amount if st["gsp_direction"]=="up" else old-amount
    if new<0:
        await m.reply_text(f"❌ قیمت «{name}» منفی می‌شود. مبلغ کاهش را کمتر کنید."); raise ApplicationHandlerStop
    B.db.conn.execute("UPDATE services SET price=? WHERE key=?",(new,key)); B.db.conn.commit()
    st["gsp_index"]=i+1; st["mode"]="gsp_direction"
    await m.reply_text(f"✅ {name}\n{old:,} → {new:,} تومان")
    await _ask(m,B,st); raise ApplicationHandlerStop
def install(app,B):
    if getattr(B,"_global_service_price_seq_v1",False): return True
    app.add_handler(CallbackQueryHandler(lambda u,c:cb(u,c,B),pattern=r"^(adm:price_seq|gsp:(up|down|skip|cancel))$"),group=-14000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:txt(u,c,B)),group=-13999)
    B._global_service_price_seq_v1=True
    return True
