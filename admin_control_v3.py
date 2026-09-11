"""Service editor and stable admin action routing."""
import logging
log=logging.getLogger("netyar.admin_v3")


def install():
    import bot as B
    if getattr(B,"_admin_v3_installed",False): return
    old_router=B.router
    async def router(update,context):
        uid=update.effective_user.id; text=(getattr(update.message,"text","") or "").strip(); st=B.S.setdefault(uid,{})
        if B.admin(uid):
            mode=st.get("admin_mode")
            if mode=="services":
                rows=B.db.conn.execute("SELECT * FROM services ORDER BY id").fetchall()
                for r in rows:
                    if str(r["key"]) in text:
                        st["service_key"]=r["key"]; st["admin_mode"]="service_action"
                        return await update.message.reply_text(
                            f"🔧 {r['name']}\n💰 {int(r['price'] or 0):,} تومان\n📌 {'باز' if r['active'] else 'بسته'}",
                            reply_markup=B.kb([["🔄 تغییر وضعیت","✏️ ویرایش نام"],["💰 ویرایش قیمت"],["⬅️ بازگشت"]])
                        )
            if mode=="service_action":
                key=st.get("service_key")
                if text=="🔄 تغییر وضعیت" and key:
                    r=B.db.conn.execute("SELECT active FROM services WHERE key=?",(key,)).fetchone()
                    if r:
                        new=0 if int(r["active"] or 0) else 1; B.db.conn.execute("UPDATE services SET active=? WHERE key=?",(new,key));B.db.conn.commit()
                        st["admin_mode"]="services"
                        return await update.message.reply_text(("🟢 خدمت باز شد." if new else "🔴 خدمت بسته شد."),reply_markup=B.kb([["🔧 مدیریت خدمات"],["⬅️ بازگشت"]]))
                if text=="✏️ ویرایش نام" and key:
                    st["admin_mode"]="service_name";return await update.message.reply_text("✏️ نام جدید خدمت را ارسال کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
                if text=="💰 ویرایش قیمت" and key:
                    st["admin_mode"]="service_price";return await update.message.reply_text("💰 قیمت جدید را فقط به تومان و به صورت عدد ارسال کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
            if mode=="service_name" and st.get("service_key"):
                key=st["service_key"]
                B.db.conn.execute("UPDATE services SET name=? WHERE key=?",(text,key));B.db.conn.commit()
                st["admin_mode"]="services";return await update.message.reply_text("✅ نام خدمت تغییر کرد.",reply_markup=B.kb([["🔧 مدیریت خدمات"],["⬅️ بازگشت"]]))
            if mode=="service_price" and st.get("service_key"):
                raw=text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")).replace(",","").replace("٬","").replace(" ","")
                if not raw.isdigit(): return await update.message.reply_text("❌ قیمت باید عدد باشد.")
                key=st["service_key"]; amount=int(raw); B.db.conn.execute("UPDATE services SET price=? WHERE key=?",(amount,key));B.db.set_setting("price_"+key,amount);B.db.conn.commit()
                st["admin_mode"]="services";return await update.message.reply_text(f"✅ قیمت به {amount:,} تومان تغییر کرد.",reply_markup=B.kb([["🔧 مدیریت خدمات"],["⬅️ بازگشت"]]))
        return await old_router(update,context)
    B.router=router
    B._admin_v3_installed=True
    log.info("admin control v3 installed")
