"""Small follow-up for production_final_patch service state routing."""
import logging
log=logging.getLogger("netyar.production_hotfix")

def install():
    import bot as B
    if getattr(B,"_production_hotfix_installed",False): return
    old=B.router
    async def router(update,context):
        uid=update.effective_user.id; text=(getattr(update.message,"text","") or "").strip(); st=B.S.setdefault(uid,{})
        if B.admin(uid):
            mode=st.get("production_admin_mode")
            if mode=="services":
                import production_final_patch as P
                if text=="⬅️ منوی مدیریت":
                    st["production_admin_mode"]=None
                    return await update.message.reply_text("🛠 پنل مدیریت کامل",reply_markup=B.amenu())
                key=next((k for k in P.CATALOG if k in text),None)
                if key:
                    st["production_service_key"]=key; st["production_admin_mode"]="service_action"
                    return await update.message.reply_text(f"🔧 {P._label(B,key,'fa')}\n📌 وضعیت: {'باز' if P._active(B,key) else 'بسته'}\n💰 قیمت: {P._price(B,key):,} تومان",reply_markup=B.kb([["🔄 باز/بسته"],["✏️ متن فارسی","✏️ English"],["✏️ العربية","💰 قیمت"],["⬅️ بازگشت"]]))
            if mode=="service_action":
                import production_final_patch as P
                key=st.get("production_service_key")
                if key:
                    if text in {"⬅️ بازگشت","⬅️ منوی مدیریت"}:
                        st["production_admin_mode"]="services"
                        return await update.message.reply_text("🔧 مدیریت خدمات",reply_markup=B.kb(P._service_admin_rows(B)))
                    if text=="🔄 باز/بسته":
                        new="0" if P._active(B,key) else "1"; B.db.set_setting("service_active_"+key,new)
                        return await update.message.reply_text("🟢 خدمت باز شد." if new=="1" else "🔴 خدمت بسته شد.",reply_markup=B.kb(P._service_admin_rows(B)))
                    lang={"✏️ متن فارسی":"fa","✏️ English":"en","✏️ العربية":"ar"}.get(text)
                    if lang:
                        st["production_label_lang"]=lang; st["production_admin_mode"]="service_label"
                        return await update.message.reply_text("✏️ متن جدید این بخش را ارسال کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
                    if text=="💰 قیمت":
                        st["production_admin_mode"]="service_price"
                        return await update.message.reply_text("💰 قیمت جدید را به تومان وارد کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
            if mode=="service_label" and st.get("production_service_key"):
                import production_final_patch as P
                if text=="⬅️ بازگشت":
                    st["production_admin_mode"]="service_action"
                    return await update.message.reply_text("🔧 گزینه خدمت را انتخاب کنید:",reply_markup=B.kb([["🔄 باز/بسته"],["✏️ متن فارسی","✏️ English"],["✏️ العربية","💰 قیمت"],["⬅️ بازگشت"]]))
                key=st["production_service_key"]; lang=st.get("production_label_lang","fa")
                B.db.set_setting(f"service_label_{key}_{lang}",text)
                st["production_admin_mode"]="services"
                return await update.message.reply_text("✅ متن ذخیره شد.",reply_markup=B.kb(P._service_admin_rows(B)))
            if mode=="service_price" and st.get("production_service_key"):
                import production_final_patch as P
                if text=="⬅️ بازگشت":
                    st["production_admin_mode"]="service_action"
                    return await update.message.reply_text("🔧 گزینه خدمت را انتخاب کنید:",reply_markup=B.kb([["🔄 باز/بسته"],["✏️ متن فارسی","✏️ English"],["✏️ العربية","💰 قیمت"],["⬅️ بازگشت"]]))
                raw=P._digits(text).replace(",","").replace("٬","").replace(" ","").replace("تومان","")
                if not raw.isdigit(): return await update.message.reply_text("❌ قیمت باید عدد باشد.")
                key=st["production_service_key"]; amount=int(raw)
                B.db.set_setting("service_price_"+key,amount);B.db.set_setting("price_"+key,amount)
                B.db.conn.execute("UPDATE services SET price=? WHERE key=?",(amount,key));B.db.conn.commit()
                st["production_admin_mode"]="services"
                return await update.message.reply_text(f"✅ قیمت به {amount:,} تومان تغییر کرد.",reply_markup=B.kb(P._service_admin_rows(B)))
        return await old(update,context)
    B.router=router;B._production_hotfix_installed=True
    log.info("production service hotfix installed")
