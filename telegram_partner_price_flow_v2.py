"""Simple exact per-partner price flow: phone -> service -> final price."""
import re
from datetime import datetime, timezone
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

def _now(): return datetime.now(timezone.utc).isoformat()

def install(app, B):
    if getattr(B, "_partner_price_flow_v2", False): return
    import partner_pricing as P
    import admin_control_v5 as A

    async def handler(update, context):
        uid = update.effective_user.id
        if not B.admin(uid) or not update.message: return
        text = (update.message.text or "").strip()
        st = B.S.setdefault(uid,{})
        mode = st.get("mode")

        if text == "📈 کاهش/افزایش قیمت همکار خاص":
            st["mode"]="pp2_phone"
            return await update.message.reply_text("📱 شماره موبایل همکار را وارد کنید:")

        if mode == "pp2_phone":
            p = P._find_partner(B.db, text)
            if not p: return await update.message.reply_text("❌ همکار پیدا نشد. شماره موبایل را دوباره وارد کنید.")
            st.update(pp2_partner_id=int(p["id"]), mode="pp2_service")
            services = "\n".join(f"• {r['key']} — {r['name']} — {int(r['price'] or 0):,} تومان" for r in P._services(B.db))
            return await update.message.reply_text(
                f"👤 همکار: {p['name'] or '-'} | 📱 {p['phone']}\n\nخدمت موردنظر را از فهرست زیر انتخاب کنید و نام یا کلید آن را ارسال کنید:\n{services}"
            )

        if mode == "pp2_service":
            key=text.split("|")[0].strip()
            row=B.db.conn.execute("SELECT key,name,price FROM services WHERE key=?",(key,)).fetchone()
            if not row:
                # Also accept an exact service name.
                row=B.db.conn.execute("SELECT key,name,price FROM services WHERE name=?",(text,)).fetchone()
            if not row: return await update.message.reply_text("❌ خدمت پیدا نشد. لطفاً نام یا کلید خدمت را از فهرست بالا ارسال کنید.")
            current=B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",(st["pp2_partner_id"],row["key"])).fetchone()
            st.update(pp2_service_key=row["key"], pp2_service_name=row["name"], pp2_current=int(current["price"]) if current else int(row["price"] or 0), mode="pp2_price")
            return await update.message.reply_text(
                f"💰 خدمت: {row['name']}\nقیمت فعلی: {st['pp2_current']:,} تومان\n\nقیمت جدید این همکار را به تومان وارد کنید:"
            )

        if mode == "pp2_price":
            raw=re.sub(r"[٬,\s]","",text)
            if not raw.isdigit(): return await update.message.reply_text("❌ فقط عدد وارد کنید؛ مثال: 420000")
            value=int(raw)
            if value < 0: return await update.message.reply_text("❌ قیمت نمی‌تواند منفی باشد.")
            B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",(st["pp2_partner_id"],st["pp2_service_key"],value,_now()))
            B.db.conn.commit()
            st["mode"]="v5"
            return await update.message.reply_text(
                f"✅ قیمت ثبت شد.\n👤 همکار: {st.get('pp2_partner_id')}\n💰 خدمت: {st['pp2_service_name']}\n💵 قیمت جدید: {value:,} تومان",
                reply_markup=A.menu(B),
            )

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-5001)
    B._partner_price_flow_v2=True
