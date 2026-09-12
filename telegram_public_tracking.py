"""Public Telegram tracking-code lookup."""
from telegram.ext import MessageHandler, filters

def install(app,B):
    if getattr(B,"_public_tracking_installed",False): return
    async def text(update,context):
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        if st.get("mode")!="public_tracking": return
        t=(update.effective_message.text or "").strip()
        if t==B.CANCEL:
            st["mode"]=None
            return await B.cancel(update,context)
        r=B.db.conn.execute("SELECT * FROM requests WHERE tracking_code=? ORDER BY id DESC LIMIT 1",(t,)).fetchone()
        if not r:
            return await update.effective_message.reply_text("❌ کد پیگیری پیدا نشد.\nکد را دقیقاً وارد کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
        answers=B.db.conn.execute("SELECT field_key,answer FROM request_answers WHERE request_id=? AND answer<>'' ORDER BY id",(r["id"],)).fetchall()
        note=next((a["answer"] for a in answers if a["field_key"] in {"admin_note","status_note","tracking_note"}),"")
        st["mode"]=None
        text=(f"🎫 کد پیگیری: {r['tracking_code']}\n\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n💰 مبلغ: {int(r['amount'] or 0):,} تومان\n💳 پرداخت: {r['payment_status']}")
        if note:text += f"\n📝 توضیح مدیریت: {note}"
        return await update.effective_message.reply_text(text,reply_markup=B.main(uid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-3400)
    B._public_tracking_installed=True
