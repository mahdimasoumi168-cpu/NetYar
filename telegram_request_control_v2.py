"""Stable manager request review and ten-stage partner-code exchange.

Payment safety: a request cannot be marked completed until its payment is
explicitly verified. Since the current Variza integration is a payment URL
without a verified callback/API in this project, the manager can confirm a
payment manually; the bot never treats a link click as proof of payment.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

def partner_uid(B,pid):
    r=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(pid,)).fetchone()
    return int(r["telegram_user_id"]) if r and str(r["telegram_user_id"]).isdigit() else None

def menu(rid, paid=False):
    rows=[[InlineKeyboardButton("🔎 جزئیات کامل",callback_data=f"rq:detail:{rid}")],
          [InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")]]
    if paid:
        rows.append([InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"rq:approve:{rid}")])
    else:
        rows.append([InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"rq:payconfirm:{rid}")])
        rows.append([InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}")])
    rows.append([InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")])
    return InlineKeyboardMarkup(rows)

async def cb(update,context,B):
    q=update.callback_query; d=(q.data or "").split(":")
    if not q or len(d)<3 or d[0]!="rq":return
    if not B.admin(q.from_user.id): await q.answer("دسترسی ندارید",show_alert=True);return
    await q.answer();rid=int(d[2]);r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
    if not r:return await q.message.reply_text("❌ درخواست پیدا نشد.")
    action=d[1]
    paid=str(r["payment_status"] or "").lower()=="paid"
    if action=="detail":
        ans=B.db.conn.execute("SELECT key,answer FROM request_answers WHERE request_id=?",(rid,)).fetchall()
        lines=[f"🎫 کد پیگیری: {r['tracking_code']}",f"🧾 خدمت: {r['service_key']}",f"📌 وضعیت: {r['status']}",f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",f"💳 پرداخت: {'تأیید شده' if paid else 'تأیید نشده'}"]+[f"{a['key']}: {a['answer']}" for a in ans if a['answer']]
        return await q.message.reply_text("🔎 بررسی جزئیات درخواست\n\n"+"\n".join(lines),reply_markup=menu(rid,paid))
    if action=="payconfirm":
        if paid:return await q.message.reply_text("ℹ️ این پرداخت قبلاً تأیید شده است.",reply_markup=menu(rid,True))
        B.db.conn.execute("UPDATE requests SET payment_status='paid',payment_method='manual_admin',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
        return await q.message.reply_text("✅ دریافت وجه توسط مدیریت تأیید شد. اکنون امکان انجام خدمت فعال است.",reply_markup=menu(rid,True))
    if action in {"review","approve","reject"}:
        if action=="approve" and not paid:
            return await q.message.reply_text("⛔ این درخواست هنوز پرداخت تأییدشده ندارد. ابتدا «💰 تأیید دریافت وجه» را بزنید.",reply_markup=menu(rid,False))
        if action=="reject":
            status="rejected"
        elif action=="review":
            status="reviewing"
        else:
            status="completed"
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid));B.db.conn.commit()
        return await q.message.reply_text("✅ وضعیت درخواست بروزرسانی شد.",reply_markup=menu(rid,paid))
    if action=="ask":
        pid=r["user_id"];target=partner_uid(B,pid)
        if not target:return await q.message.reply_text("❌ تلگرام همکار برای این درخواست متصل نیست.")
        st=B.S.setdefault(q.from_user.id,{});st.update(code_request_id=rid,code_partner_id=pid,code_stage=1)
        await context.bot.send_message(target,f"🔐 درخواست کد مدیریت\n🎫 {r['tracking_code']}\n\nمرحله ۱ از ۱۰\nکد مرحله ۱ را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📨 ارسال کد مرحله ۱",callback_data=f"rqcode:send:{rid}:1")]]))
        return await q.message.reply_text("📨 مرحله ۱ برای همکار ارسال شد.",reply_markup=menu(rid,paid))

async def code_cb(update,context,B):
    q=update.callback_query;d=(q.data or "").split(":")
    if not q or len(d)<4 or d[0]!="rqcode":return
    rid=int(d[2]);stage=int(d[3]);uid=q.from_user.id;st=B.S.setdefault(uid,{})
    if d[1]=="send":
        r=B.db.conn.execute("SELECT user_id FROM requests WHERE id=?",(rid,)).fetchone()
        if not r or str(st.get("partner_id"))!=str(r["user_id"]):return await q.answer("این درخواست متعلق به شما نیست.",show_alert=True)
        st.update(mode="partner_send_code",code_request_id=rid,code_stage=stage);await q.answer();return await q.message.reply_text(f"🔐 کد مرحله {stage} را همینجا ارسال کنید:")
    if d[1]=="next" and B.admin(uid):
        pid=st.get("code_partner_id");target=partner_uid(B,pid)
        if not target:return await q.message.reply_text("❌ همکار در دسترس نیست.")
        nxt=min(10,stage+1);st["code_stage"]=nxt
        await context.bot.send_message(target,f"🔐 مرحله {nxt} از ۱۰\nکد مرحله {nxt} را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📨 ارسال کد مرحله {nxt}",callback_data=f"rqcode:send:{rid}:{nxt}")]]))
        return await q.message.reply_text(f"📨 مرحله {nxt} ارسال شد.")
    if d[1]=="finish" and B.admin(uid):return await q.message.reply_text("✅ دریافت کدها پایان یافت.")

async def code_text(update,context,B):
    if not update.message:return
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    if st.get("mode")!="partner_send_code":return
    rid=int(st.get("code_request_id"));stage=int(st.get("code_stage",1));text=(update.message.text or "").strip()
    r=B.db.conn.execute("SELECT user_id,tracking_code FROM requests WHERE id=?",(rid,)).fetchone()
    if not r or str(st.get("partner_id"))!=str(r["user_id"]):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_codes(request_id INTEGER,stage INTEGER,code TEXT,created_at TEXT,PRIMARY KEY(request_id,stage))")
    B.db.conn.execute("INSERT OR REPLACE INTO request_partner_codes VALUES(?,?,?,?)",(rid,stage,text,B.now()));B.db.conn.commit()
    for aid in B.ADM:
        try:
            buttons=[]
            if stage<10:buttons.append(InlineKeyboardButton(f"➡️ مرحله {stage+1}",callback_data=f"rqcode:next:{rid}:{stage}"))
            buttons.append(InlineKeyboardButton("✅ پایان",callback_data=f"rqcode:finish:{rid}:{stage}"))
            await context.bot.send_message(int(aid),f"🔐 کد همکار دریافت شد\n🎫 {r['tracking_code']}\nمرحله {stage} از ۱۰\nکد: {text}",reply_markup=InlineKeyboardMarkup([buttons]))
        except Exception:pass
    st["mode"]=None;return await update.message.reply_text(f"✅ کد مرحله {stage} برای مدیریت ارسال شد.")

def install(app,B):
    if getattr(B,"_request_control_v2",False):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_codes(request_id INTEGER,stage INTEGER,code TEXT,created_at TEXT,PRIMARY KEY(request_id,stage))");B.db.conn.commit()
    app.add_handler(CallbackQueryHandler(lambda u,c:cb(u,c,B),pattern=r"^rq:"),group=-50)
    app.add_handler(CallbackQueryHandler(lambda u,c:code_cb(u,c,B),pattern=r"^rqcode:"),group=-49)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:code_text(u,c,B)),group=-48)
    B._request_control_v2=True
