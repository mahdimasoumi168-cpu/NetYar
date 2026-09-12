"""Per-partner service pricing and admin controls.

The public service price remains the default. A partner-specific price is used
only when an admin explicitly creates an override for that partner and service.
"""
import re
from datetime import datetime, timezone
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

_INSTALLED = False

def _now():
    return datetime.now(timezone.utc).isoformat()

def ensure(db):
    db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
        partner_id INTEGER NOT NULL,
        service_key TEXT NOT NULL,
        price INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(partner_id,service_key)
    )""")
    db.conn.commit()

def price(db, service_key, partner_id=None, default=None):
    ensure(db)
    if partner_id:
        r=db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(partner_id,service_key)).fetchone()
        if r:
            return int(r["price"])
    if default is not None:
        return int(default)
    r=db.conn.execute("SELECT price FROM services WHERE key=?",(service_key,)).fetchone()
    if r:
        return int(r["price"] or 0)
    return 0

def _find_partner(db, value):
    v=str(value or "").strip()
    if v.isdigit():
        r=db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=?",(int(v),v)).fetchone()
    else:
        r=db.conn.execute("SELECT * FROM partners WHERE phone=? OR name LIKE ? ORDER BY id LIMIT 1",(v,f"%{v}%")).fetchone()
    return r

def _services(db):
    return db.conn.execute("SELECT key,name,price FROM services ORDER BY id").fetchall()

def _menu(base):
    rows=list(base or [])
    if not any(any("قیمت ویژه همکاران" in str(x[1] if isinstance(x,(tuple,list)) and len(x)>1 else x) for x in row) for row in rows):
        rows.insert(4,[("🎁 partner_prices","🎁 قیمت ویژه همکاران")])
    return rows

def install_telegram(app, B):
    ensure(B.db)
    import admin_control_v5 as A
    old_menu=A.menu
    A.menu=lambda bot: old_menu(bot)+[["🎁 قیمت ویژه همکاران"]]
    async def handler(update, context):
        uid=update.effective_user.id
        if not B.admin(uid): return
        t=(update.message.text or "").strip()
        st=B.S.setdefault(uid,{})
        mode=st.get("mode")
        if t in {"🎁 قیمت ویژه همکاران","🎁 partner_prices"}:
            st["mode"]="pp_partner"
            return await update.message.reply_text("🎁 قیمت ویژه همکاران\n\nشناسه یا شماره تلفن همکار را ارسال کنید:")
        if mode=="pp_partner":
            p=_find_partner(B.db,t)
            if not p:
                return await update.message.reply_text("❌ همکار پیدا نشد. شناسه یا شماره تلفن را درست وارد کنید.")
            st["pp_partner_id"]=int(p["id"]); st["mode"]="pp_service"
            lines=[f"👤 همکار: {p['name'] or '-'} | 📱 {p['phone']}\n","کلید خدمت را ارسال کنید:"]
            lines.append("\n".join(f"• {r['key']} — {r['name']} — قیمت عمومی {int(r['price']):,}" for r in _services(B.db)))
            return await update.message.reply_text("\n".join(lines))
        if mode=="pp_service":
            key=t.split("|")[0].strip()
            r=B.db.conn.execute("SELECT key,name,price FROM services WHERE key=?",(key,)).fetchone()
            if not r:
                return await update.message.reply_text("❌ کلید خدمت پیدا نشد. یکی از کلیدهای فهرست را ارسال کنید.")
            st["pp_service_key"]=key; st["mode"]="pp_price"
            current=B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(st["pp_partner_id"],key)).fetchone()
            shown=int(current["price"]) if current else int(r["price"])
            return await update.message.reply_text(f"💰 خدمت: {r['name']}\nقیمت عمومی: {int(r['price']):,} تومان\nقیمت فعلی این همکار: {shown:,} تومان\n\nقیمت ویژه جدید را به تومان ارسال کنید.\nبرای حذف تخفیف: 0")
        if mode=="pp_price":
            raw=re.sub(r"[٬,\s]", "", t)
            if not raw.isdigit():
                return await update.message.reply_text("❌ فقط عدد وارد کنید.")
            value=int(raw); pid=st["pp_partner_id"]; key=st["pp_service_key"]
            if value==0:
                B.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key))
                msg="🗑 قیمت ویژه حذف شد و قیمت عمومی برای این همکار فعال شد."
            else:
                B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices(partner_id,service_key,price,updated_at) VALUES(?,?,?,?)",(pid,key,value,_now()))
                msg=f"✅ قیمت ویژه ثبت شد: {value:,} تومان"
            B.db.conn.commit(); st["mode"]="v5"
            return await update.message.reply_text(msg+"\n\n👤 فقط برای همین همکار اعمال می‌شود.",reply_markup=A.menu(B))
        return
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handler),group=-7)

def install_rubika(R):
    ensure(R.db)
    old_rows=R.admin_rows
    R.admin_rows=lambda: old_rows()+[[('18','🎁 قیمت ویژه همکاران')]]
    old_admin=R.admin
    def admin(uid,chat,x):
        st=R.STATE.setdefault(str(uid),{}); x=str(x).strip(); step=st.get("step")
        if x in {"18","🎁 قیمت ویژه همکاران"}:
            st["step"]="pp_partner"; return R.send(chat,"🎁 قیمت ویژه همکاران\nشناسه یا شماره تلفن همکار را ارسال کنید.",[[('0','⬅️ مدیریت')]])
        if step=="pp_partner":
            p=_find_partner(R.db,x)
            if not p:return R.send(chat,"❌ همکار پیدا نشد. دوباره شناسه یا شماره تلفن را بفرستید.")
            st["pp_partner_id"]=int(p["id"]);st["step"]="pp_service"
            return R.send(chat,"👤 همکار: {}\nکلید خدمت را ارسال کنید:\n{}".format(p['name'] or '-',"\n".join(f"• {r['key']} — {r['name']} — {int(r['price']):,}" for r in _services(R.db))))
        if step=="pp_service":
            r=R.db.conn.execute("SELECT key,name,price FROM services WHERE key=?",(x.split('|')[0].strip(),)).fetchone()
            if not r:return R.send(chat,"❌ کلید خدمت پیدا نشد.")
            st["pp_service_key"]=x.split('|')[0].strip();st["step"]="pp_price"
            cur=R.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(st["pp_partner_id"],st["pp_service_key"])).fetchone()
            return R.send(chat,f"💰 {r['name']}\nقیمت عمومی: {int(r['price']):,}\nقیمت فعلی همکار: {int(cur['price']) if cur else int(r['price']):,}\nقیمت ویژه جدید را بفرستید؛ برای حذف 0")
        if step=="pp_price":
            raw=re.sub(r"[٬,\s]",'',x)
            if not raw.isdigit():return R.send(chat,"❌ فقط عدد وارد کنید.")
            pid=st["pp_partner_id"];key=st["pp_service_key"];v=int(raw)
            if v==0:
                R.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",(pid,key));msg="🗑 قیمت ویژه حذف شد."
            else:
                R.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(pid,key,v,_now()));msg=f"✅ قیمت ویژه {v:,} تومان ثبت شد."
            R.db.conn.commit();st["step"]="admin";return R.send(chat,msg+"\n👤 فقط برای همین همکار اعمال می‌شود.",R.admin_rows())
        return old_admin(uid,chat,x)
    R.admin=admin
