"""Final payment router for every paid Telegram service.
Partners are charged from balance atomically. Customers get a card-to-card
invoice and the request is not sent to management until a receipt exists.
"""
import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop
from payment_invoice import invoice_text, invoice_markup

def _card(B):
    return (os.getenv("PAYMENT_CARD","").strip() or B.db.setting("card_number","").strip(),
            os.getenv("PAYMENT_CARD_OWNER","").strip() or B.db.setting("card_owner","").strip())

def install(app,B):
    if getattr(B,"_final_payment_router_v1",False): return True

    async def print_finish(update,context):
        msg=update.effective_message; u=update.effective_user
        if not msg or not u: return
        st=B.S.setdefault(u.id,{})
        if st.get("mode")!="print" or (msg.text or "").strip()!="تأیید": return
        files=list(st.get("files") or [])
        if not files:
            await msg.reply_text("❌ حداقل یک فایل برای چاپ ارسال کنید.")
            raise ApplicationHandlerStop
        amount=len(files)*int(B.db.setting("price_print_bw","0") or 0)
        if amount<=0:
            amount=int(B.db.setting("price_print_bw","0") or 0)
            if amount<=0:
                await msg.reply_text("❌ قیمت چاپ هنوز توسط مدیریت تعیین نشده است.")
                raise ApplicationHandlerStop
        pid=st.get("partner_id")
        if pid:
            try:
                conn=B.db.conn; conn.execute("BEGIN IMMEDIATE")
                p=conn.execute("SELECT id,name,balance,active FROM partners WHERE id=? AND active=1",(int(pid),)).fetchone()
                bal=int(p["balance"] or 0) if p else 0
                if not p or bal<amount:
                    conn.rollback()
                    await msg.reply_text(f"❌ اعتبار پنل همکاران کافی نیست.\\n\\n💳 اعتبار: {bal:,} تومان\\n💰 هزینه چاپ: {amount:,} تومان\\n➕ نیاز به شارژ: {max(0,amount-bal):,} تومان",reply_markup=B.partner_kb(st.get("lang","fa")))
                    raise ApplicationHandlerStop
                cur=conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?",(amount,B.now(),int(pid),amount))
                if cur.rowcount!=1:
                    conn.rollback(); await msg.reply_text("❌ کسر اعتبار انجام نشد؛ مبلغی کسر نشده است. دوباره تلاش کنید.",reply_markup=B.partner_kb(st.get("lang","fa"))); raise ApplicationHandlerStop
                rid,code=B.db.create_request(int(pid),"print","telegram",amount)
                for i,fid in enumerate(files,1): B.db.answer(rid,f"file_{i}",file_id=fid)
                conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid))
                conn.commit()
            except ApplicationHandlerStop: raise
            except Exception:
                try:B.db.conn.rollback()
                except Exception:pass
                raise
            await B.notify_admins(context.application,f"🆕 درخواست چاپ همکار\\n🎫 {code}\\n💰 مبلغ: {amount:,} تومان\\n💳 پرداخت: اعتبار پنل همکاران\\n📎 تعداد فایل: {len(files)}",rid)
            st["mode"]=None; st["request_id"]=rid
            await msg.reply_text(f"✅ درخواست چاپ ثبت شد و {amount:,} تومان از اعتبار کسر شد.\\n🎫 {code}",reply_markup=B.partner_kb(st.get("lang","fa")))
            raise ApplicationHandlerStop

        owner=B.db.user("telegram",u.id,u.username,u.full_name)
        rid,code=B.db.create_request(owner,"print","telegram",amount)
        for i,fid in enumerate(files,1): B.db.answer(rid,f"file_{i}",file_id=fid)
        B.db.conn.execute("UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='invoice',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
        st["mode"]="invoice_pending";st["request_id"]=rid;st["tracking_code"]=code
        await msg.reply_text(invoice_text("فاکتور خدمات چاپ",amount,code,B),reply_markup=invoice_markup(B),parse_mode="HTML")
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,print_finish),group=-109998)
    B._final_payment_router_v1=True
    return True
