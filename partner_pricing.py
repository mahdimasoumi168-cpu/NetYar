"""Per-partner service pricing and admin controls."""
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from telegram.ext import MessageHandler, filters

_ACTIVE_PARTNER=ContextVar("netyar_active_partner",default=None)

def _now(): return datetime.now(timezone.utc).isoformat()

def ensure(db):
    db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
        partner_id INTEGER NOT NULL, service_key TEXT NOT NULL, price INTEGER NOT NULL,
        updated_at TEXT NOT NULL, PRIMARY KEY(partner_id,service_key))""")
    db.conn.commit()

def price(db,service_key,partner_id=None,default=None):
    ensure(db)
    if partner_id:
        r=db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(partner_id,service_key)).fetchone()
        if r:return int(r["price"])
    if default is not None:return int(default)
    r=db.conn.execute("SELECT price FROM services WHERE key=?",(service_key,)).fetchone()
    return int(r["price"] or 0) if r else 0

def _find_partner(db,value):
    v=str(value or "").strip()
    if v.isdigit(): return db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=?",(int(v),v)).fetchone()
    return db.conn.execute("SELECT * FROM partners WHERE phone=? OR name LIKE ? ORDER BY id LIMIT 1",(v,f"%{v}%")).fetchone()

def _services(db): return db.conn.execute("SELECT key,name,price FROM services ORDER BY id").fetchall()

def _patch_setting(db):
    if getattr(db,"_partner_price_setting_patch",False): return
    old=db.setting
    def setting(key,default=""):
        pid=_ACTIVE_PARTNER.get()
        if pid and key.startswith("price_"):
            service={"price_government":"government","price_fida":"fida","price_print_bw":"print_bw","price_print_color":"print_color"}.get(key)
            if service:
                return str(price(db,service,pid,default))
        return old(key,default)
    db.setting=setting;db._partner_price_setting_patch=True

def install_telegram(app,B):
    ensure(B.db);_patch_setting(B.db)
    import admin_control_v5 as A
    old_menu=A.menu
    A.menu=lambda bot: old_menu(bot)+[["🎁 قیمت ویژه همکاران"]]
    async def handler(update,context):
        uid=update.effective_user.id
        if not B.admin(uid):return
        t=(update.message.text or "").strip();st=B.S.setdefault(uid,{});mode=st.get("mode")
        if t=="🎁 قیمت ویژه همکاران":
            st["mode"]="pp_partner";return await update.message.reply_text("🎁 قیمت ویژه همکاران\n\nشناسه یا شماره تلفن همکار را ارسال کنید:")
        if mode=="pp_partner":
            p=_find_partner(B.db,t)
            if not p:return await update.message.reply_text("❌ همکار پیدا نشد.")
            st["pp_partner_id"]=int(p["id"]);st["mode"]="pp_service"
            return await update.message.reply_text("👤 همکار: {} | 📱 {}\n\nکلید خدمت را ارسال کنید:\n{}".format(p["name"] or "-",p["phone"],"\n".join(f"• {r['key']} — {r['name']} — {int(r['price']):,} تومان" for r in _services(B.db))))
        if mode=="pp_service":
            key=t.split("|")[0].strip();r=B.db.conn.execute("SELECT key,name,price FROM services WHERE key=?",(key,)).fetchone()
            if not r:return await update.message.reply_text("❌ کلید خدمت پیدا نشد.")
            st["pp_service_key"]=key;st["mode"]="pp_price";cur=B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(st["pp_partner_id"],key)).fetchone();shown=int(cur["price"]) if cur else int(r["price"])
            return await update.message.reply_text(f"💰 {r['name']}\nقیمت عمومی: {int(r['price']):,} تومان\nقیمت فعلی همکار: {shown:,} تومان\n\nقیمت ویژه جدید را بفرستید.\nبرای حذف قیمت ویژه: 0")
        if mode=="pp_price":
            raw=re.sub(r"[٬,\s]","",t)
            if not raw.isdigit():return await update.message.reply_text("❌ فقط عدد وارد کنید.")
            pid=st["pp_partner_id"];key=st["pp_service_key"];v=int(raw)
            if v==0:B.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key));msg="🗑 قیمت ویژه حذف شد و قیمت عمومی فعال شد."
            else:B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(pid,key,v,_now()));msg=f"✅ قیمت ویژه {v:,} تومان ثبت شد."
            B.db.conn.commit();st["mode"]="v5";return await update.message.reply_text(msg+"\n👤 فقط برای همین همکار اعمال می‌شود.",reply_markup=A.menu(B))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handler),group=-7)
    # The government media handler reads db.setting("price_government"). Wrap it
    # with a request-scoped partner id, without changing shared global pricing.
    import telegram_ux_billing as U
    old_media=U._gov_media
    async def priced_media(update,context):
        pid=B.S.get(update.effective_user.id,{}).get("partner_id")
        tok=_ACTIVE_PARTNER.set(pid)
        try:return await old_media(update,context)
        finally:_ACTIVE_PARTNER.reset(tok)
    U._gov_media=priced_media

def install_rubika(R):
    ensure(R.db);_patch_setting(R.db)
    old_rows=R.admin_rows;R.admin_rows=lambda:old_rows()+[[('18','🎁 قیمت ویژه همکاران')]]
    old_admin=R.admin
    def admin(uid,chat,x):
        st=R.STATE.setdefault(str(uid),{});x=str(x).strip();step=st.get("step")
        if x in {"18","🎁 قیمت ویژه همکاران"}:st["step"]="pp_partner";return R.send(chat,"🎁 قیمت ویژه همکاران\nشناسه یا شماره تلفن همکار را ارسال کنید.",[[('0','⬅️ مدیریت')]])
        if step=="pp_partner":
            p=_find_partner(R.db,x)
            if not p:return R.send(chat,"❌ همکار پیدا نشد.")
            st["pp_partner_id"]=int(p["id"]);st["step"]="pp_service";return R.send(chat,"👤 همکار: {} | 📱 {}\n\nکلید خدمت را ارسال کنید:\n{}".format(p['name'] or '-',p['phone'],"\n".join(f"• {r['key']} — {r['name']} — {int(r['price']):,}" for r in _services(R.db))))
        if step=="pp_service":
            key=x.split('|')[0].strip();r=R.db.conn.execute("SELECT key,name,price FROM services WHERE key=?",(key,)).fetchone()
            if not r:return R.send(chat,"❌ کلید خدمت پیدا نشد.")
            st["pp_service_key"]=key;st["step"]="pp_price";cur=R.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(st["pp_partner_id"],key)).fetchone();shown=int(cur['price']) if cur else int(r['price'])
            return R.send(chat,f"💰 {r['name']}\nقیمت عمومی: {int(r['price']):,}\nقیمت فعلی همکار: {shown:,}\nقیمت ویژه جدید را بفرستید؛ برای حذف 0")
        if step=="pp_price":
            raw=re.sub(r"[٬,\s]",'',x)
            if not raw.isdigit():return R.send(chat,"❌ فقط عدد وارد کنید.")
            pid=st["pp_partner_id"];key=st["pp_service_key"];v=int(raw)
            if v==0:R.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key));msg="🗑 قیمت ویژه حذف شد."
            else:R.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(pid,key,v,_now()));msg=f"✅ قیمت ویژه {v:,} تومان ثبت شد."
            R.db.conn.commit();st["step"]="admin";return R.send(chat,msg+"\n👤 فقط برای همین همکار اعمال می‌شود.",R.admin_rows())
        return old_admin(uid,chat,x)
    R.admin=admin
    old_process=R.process
    def process(update):
        uid=str(update.get("sender_id") or update.get("user_id") or update.get("chat_id") or "") if isinstance(update,dict) else ""
        pid=R.STATE.get(uid,{}).get("partner_id")
        tok=_ACTIVE_PARTNER.set(pid)
        try:return old_process(update)
        finally:_ACTIVE_PARTNER.reset(tok)
    R.process=process
