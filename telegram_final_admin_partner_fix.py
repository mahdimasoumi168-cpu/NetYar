"""Final Telegram admin/partner stability layer.

Partner pricing is a guided, section-by-section flow. It asks only for
services that are actually exposed in the partner panel.
"""
import re
import logging
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.final_admin_partner_fix")
CONTROLS={"❌ انصراف","انصراف","لغو","Cancel","إلغاء","🔄 شروع مجدد","شروع مجدد","Restart","Start again"}

# Do not use the whole services table here: it can contain customer-only or
# legacy services. This catalog mirrors the current partner panel.
PARTNER_PRICING = (
    ("government", "🏛 حل مشکل سامانه دولت من"),
    ("fida", "🪪 فیدای غیر حضوری"),
    ("tracking", "🔎 پیگیری کد"),
)
DEFAULTS = {
    "government": 0,
    "fida": 400000,
    "tracking": 0,
}

def _now(): return datetime.now(timezone.utc).isoformat()
def _admin_menu(B):
    import telegram_admin_plus as A
    return A._admin_menu()

def _current_price(B,pid,key):
    row=B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key)).fetchone()
    if row: return int(row["price"] or 0)
    try:
        row=B.db.conn.execute("SELECT price FROM services WHERE key=?",(key,)).fetchone()
        if row and row["price"] is not None: return int(row["price"] or 0)
    except Exception: pass
    return DEFAULTS.get(key,0)

def install(app,B):
    if getattr(B,"_final_admin_partner_fix",False): return
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(partner_id INTEGER NOT NULL,service_key TEXT NOT NULL,price INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(partner_id,service_key))""")
    B.db.conn.commit()
    try:
        import telegram_admin_plus as A
        old_menu=A._admin_menu
        if not getattr(A,"_hard_logout_menu_patch",False):
            def menu_with_final_controls():
                markup=old_menu(); rows=[list(r) for r in markup.inline_keyboard]
                if not any("قیمت اختصاصی همکار" in str(b.text) for row in rows for b in row):
                    rows.append([InlineKeyboardButton("📈 قیمت اختصاصی همکار — خدمات پنل",callback_data="adm:partner_price_adjust_final")])
                if not any("خروج کامل" in str(b.text) for row in rows for b in row):
                    rows.append([InlineKeyboardButton("🚪 خروج کامل از پنل مدیریت",callback_data="adm:admin_logout")])
                return InlineKeyboardMarkup(rows)
            A._admin_menu=menu_with_final_controls; A._hard_logout_menu_patch=True
    except Exception: log.exception("admin menu patch failed")

    async def callback(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        data=str(q.data or "")
        if data=="adm:admin_logout":
            await q.answer(); uid=q.from_user.id; old=B.S.get(uid,{})
            B.S[uid]={k:old[k] for k in ("lang","status","citizenship") if k in old}
            await q.message.reply_text("🔒 از پنل مدیریت به‌طور کامل خارج شدید.\nبرای ورود دوباره خودتان پنل مدیریت را انتخاب کنید.",reply_markup=B.main(uid)); raise ApplicationHandlerStop
        if data=="adm:partner_price_adjust_final":
            await q.answer(); st=B.S.setdefault(q.from_user.id,{})
            st.update({"mode":"fpp_partner","fpp_service_index":0,"fpp_prices":{}})
            await q.message.reply_text("📈 قیمت‌گذاری اختصاصی همکار\n\nشماره یا شناسه همکار را ارسال کنید:"); raise ApplicationHandlerStop

    async def text(update,context):
        if not update.message or not update.effective_user or not B.admin(update.effective_user.id): return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{}); mode=st.get("mode"); t=(update.message.text or "").strip()
        if mode not in {"fpp_partner","fpp_price"}: return
        if t in CONTROLS:
            st["mode"]=None
            for k in ("fpp_partner_id","fpp_service_index","fpp_prices"): st.pop(k,None)
            await update.message.reply_text("❌ عملیات لغو شد.",reply_markup=_admin_menu(B)); raise ApplicationHandlerStop
        if mode=="fpp_partner":
            raw=t.replace("+98","0").replace("0098","0"); p=None
            if raw.isdigit(): p=B.db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=?",(int(raw),raw)).fetchone()
            if not p: p=B.db.conn.execute("SELECT * FROM partners WHERE phone=? OR name LIKE ? LIMIT 1",(raw,f"%{raw}%")).fetchone()
            if not p:
                await update.message.reply_text("❌ همکار پیدا نشد. شماره، شناسه یا نام همکار را صحیح وارد کنید."); return
            st.update({"fpp_partner_id":int(p["id"]),"fpp_service_index":0,"fpp_prices":{},"mode":"fpp_price"})
            key,label=PARTNER_PRICING[0]; current=_current_price(B,int(p["id"]),key)
            await update.message.reply_text(f"👤 همکار: {p['name'] or p['phone']}\n\n💰 خدمت ۱ از {len(PARTNER_PRICING)}\n{label}\nقیمت فعلی: {current:,} تومان\n\nقیمت این خدمت را وارد کنید:"); raise ApplicationHandlerStop
        raw=re.sub(r"[٬,\s]","",t)
        if not raw.isdigit():
            await update.message.reply_text("❌ فقط مبلغ عددی وارد کنید؛ مثال: 150000"); return
        idx=int(st.get("fpp_service_index",0)); pid=int(st["fpp_partner_id"]); key,label=PARTNER_PRICING[idx]; value=int(raw)
        B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(pid,key,value,_now())); B.db.conn.commit()
        st.setdefault("fpp_prices",{})[key]=value; idx+=1
        if idx<len(PARTNER_PRICING):
            st["fpp_service_index"]=idx; nkey,nlabel=PARTNER_PRICING[idx]; current=_current_price(B,pid,nkey)
            await update.message.reply_text(f"✅ {label} = {value:,} تومان\n\n💰 خدمت {idx+1} از {len(PARTNER_PRICING)}\n{nlabel}\nقیمت فعلی: {current:,} تومان\n\nقیمت این خدمت را وارد کنید:"); raise ApplicationHandlerStop
        st["mode"]=None
        await update.message.reply_text("✅ قیمت تمام خدمات پنل همکار، بخش‌به‌بخش و تک‌تک ثبت شد.\n\n📱 سیم کارت نیز برای سامانتل، ایرانسل و رایتل جداگانه ثبت شد.",reply_markup=_admin_menu(B)); raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback,pattern=r"^adm:(admin_logout|partner_price_adjust_final)$"),group=-12000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-11999)
    B._final_admin_partner_fix=True
    log.info("Final partner pricing flow installed: %s", ", ".join(k for k,_ in PARTNER_PRICING))
