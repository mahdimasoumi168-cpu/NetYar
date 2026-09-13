"""Final Telegram admin/partner stability layer.

- Hard logout from admin and partner panels.
- Per-partner pricing asks for every service one-by-one and stores the exact
  amount supplied by the administrator.
- Control buttons are navigation and never become ticket/message content.
"""
import re
import logging
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.final_admin_partner_fix")
CONTROLS = {"❌ انصراف", "انصراف", "لغو", "Cancel", "إلغاء", "🔄 شروع مجدد", "شروع مجدد", "Restart", "Start again"}

def _now(): return datetime.now(timezone.utc).isoformat()

def _services(B):
    return B.db.conn.execute("SELECT key,name,price FROM services ORDER BY id").fetchall()

def _admin_menu(B):
    import telegram_admin_plus as A
    return A._admin_menu()

def install(app, B):
    if getattr(B, "_final_admin_partner_fix", False): return

    # Ensure exact-price storage exists.
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
        partner_id INTEGER NOT NULL, service_key TEXT NOT NULL,
        price INTEGER NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(partner_id, service_key))""")
    B.db.conn.commit()

    async def callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id): return
        data = str(q.data or "")
        if data == "adm:admin_logout":
            await q.answer()
            uid=q.from_user.id
            old=B.S.get(uid,{})
            B.S[uid]={k:old[k] for k in ("lang","status","citizenship") if k in old}
            await q.message.reply_text("🔒 از پنل مدیریت خارج شدید.\nبرای ورود دوباره باید خودتان پنل مدیریت را انتخاب کنید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop
        if data == "adm:partner_price_adjust_final":
            await q.answer()
            st=B.S.setdefault(q.from_user.id,{})
            st.update({"mode":"fpp_partner","fpp_service_index":0,"fpp_prices":{}})
            await q.message.reply_text("📈 قیمت اختصاصی همکار\n\nشماره یا شناسه همکار را ارسال کنید:")
            raise ApplicationHandlerStop

    async def text(update, context):
        if not update.message or not update.effective_user or not B.admin(update.effective_user.id): return
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        mode=st.get("mode"); t=(update.message.text or "").strip()
        if mode not in {"fpp_partner","fpp_price"}: return
        if t in CONTROLS:
            st["mode"]=None; st.pop("fpp_partner_id",None); st.pop("fpp_prices",None)
            await update.message.reply_text("❌ عملیات لغو شد.",reply_markup=_admin_menu(B)); raise ApplicationHandlerStop
        if mode == "fpp_partner":
            raw=t.replace("+98","0").replace("0098","0")
            p=B.db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=?", (int(raw),raw)).fetchone() if raw.isdigit() else None
            if not p:
                p=B.db.conn.execute("SELECT * FROM partners WHERE phone=? OR name LIKE ? LIMIT 1",(raw,f"%{raw}%")).fetchone()
            if not p:
                await update.message.reply_text("❌ همکار پیدا نشد. شماره، شناسه یا نام همکار را صحیح وارد کنید."); return
            services=_services(B)
            if not services:
                st["mode"]=None; await update.message.reply_text("❌ هیچ خدمتی تعریف نشده است.",reply_markup=_admin_menu(B)); raise ApplicationHandlerStop
            st.update({"fpp_partner_id":int(p["id"]),"fpp_service_index":0,"fpp_prices":{},"mode":"fpp_price"})
            r=services[0]
            await update.message.reply_text(f"👤 همکار: {p['name']}\n\n💰 خدمت ۱ از {len(services)}\n{r['name']}\nقیمت عمومی: {int(r['price'] or 0):,} تومان\n\nقیمت این خدمت برای این همکار را به تومان وارد کنید:")
            raise ApplicationHandlerStop
        if mode == "fpp_price":
            raw=re.sub(r"[٬,\s]","",t)
            if not raw.isdigit():
                await update.message.reply_text("❌ فقط مبلغ عددی وارد کنید؛ مثال: 150000"); return
            value=int(raw)
            services=_services(B); idx=int(st.get("fpp_service_index",0)); pid=int(st["fpp_partner_id"])
            r=services[idx]; st.setdefault("fpp_prices",{})[r["key"]]=value
            B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(pid,r["key"],value,_now())); B.db.conn.commit()
            idx+=1
            if idx < len(services):
                st["fpp_service_index"]=idx; nxt=services[idx]
                await update.message.reply_text(f"✅ {r['name']} = {value:,} تومان\n\n💰 خدمت {idx+1} از {len(services)}\n{nxt['name']}\nقیمت عمومی: {int(nxt['price'] or 0):,} تومان\n\nقیمت این خدمت برای این همکار را وارد کنید:"); raise ApplicationHandlerStop
            st["mode"]=None
            await update.message.reply_text("✅ قیمت‌های اختصاصی همه خدمات این همکار ثبت شد.\n\nهر خدمت به‌صورت جداگانه با مبلغی که شما وارد کردید ذخیره شده است.",reply_markup=_admin_menu(B)); raise ApplicationHandlerStop

    # Highest-priority final owners.
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^adm:(admin_logout|partner_price_adjust_final)$"), group=-12000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-11999)
    B._final_admin_partner_fix=True
    log.info("Final admin/partner stability layer installed")
