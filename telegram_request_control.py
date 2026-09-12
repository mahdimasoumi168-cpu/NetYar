"""Manager-side request controls and a persistent 10-stage partner code workflow."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop


def _admin(B,uid): return B.admin(uid)

def _partner_uid(B,pid):
    r=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(pid,)).fetchone()
    return int(r["telegram_user_id"]) if r and str(r["telegram_user_id"]).isdigit() else None

async def _cb(update,context,B):
    q=update.callback_query
    if not q:return
    d=(q.data or "").split(":")
    if len(d)<2 or d[0]!="panel":return
    if not _admin(B,q.from_user.id):
        await q.answer("دسترسی ندارید",show_alert=True);return
    await q.answer()
    try:rid=int(d[-1])
    except Exception:return await q.message.reply_text("❌ شناسه درخواست نامعتبر است.")
    r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
    if not r:return await q.message.reply_text("❌ درخواست پیدا نشد.")
    if d[1]=="req":
        answers=B.db.conn.execute("SELECT key,answer FROM request_answers WHERE request_id=?",(rid,)).fetchall()
        body=[f"🎫 درخواست #{rid}",f"کد پیگیری: {r['tracking_code']}",f"خدمت: {r['service_key']}",f"وضعیت: {r['status']}",f"مبلغ: {int(r['amount'] or 0):,} تومان"]
        body += [f"{a['key']}: {a['answer']}" for a in answers if a['answer']]
        return await q.message.reply_text("🔎 جزئیات کامل\n\n"+"\n".join(body),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"panel:askcode:{rid}")],[InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"panel:review:{rid}"),InlineKeyboardButton("✅ تأیید/انجام شد",callback_data=f"panel:approve:{rid}")],[InlineKeyboardButton("❌ رد درخواست",callback_data=f"panel:reject:{rid}")]]))
    if d[1] in {"review","approve","reject"}:
        status={"review":"reviewing","approve":"completed","reject":"rejected"}[d[1]]
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid));B.db.conn.commit()
        return await q.message.reply_text("✅ وضعیت درخواست به «در حال بررسی» تغییر کرد." if d[1]=="review" else "✅ درخواست انجام شد." if d[1]=="approve" else "❌ درخواست رد شد.")
    if d[1]=="askcode":
        pid=r["user_id"]
        target=_partner_uid(B,pid)
        if not target:return await q.message.reply_text("❌ حساب تلگرام این همکار هنوز به پنل متصل نشده است.")
        st=B.S.setdefault(q.from_user.id,{})
        st.update(code_request_id=rid,code_partner_id=pid,code_stage=1)
        p=B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?",(pid,)).fetchone()
        await context.bot.send_message(target,f"🔐 درخواست کد از مدیریت\n🎫 درخواست: {r['tracking_code']}\n👤 همکار: {p['name'] if p else '-'}\n\nمرحله ۱ از ۱۰\nکد موردنظر را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📨 ارسال کد مرحله ۱",callback_data=f"code:send:{rid}:1")]]))
        return await q.message.reply_text("📨 درخواست کد مرحله ۱ برای همکار ارسال شد. حداکثر ۱۰ مرحله پشتیبانی می‌شود.")

async def _code_cb(update,context,B):
    q=update.callback_query
    if not q:return
    d=(q.data or "").split(":")
    if len(d)<3 or d[0]!="code":return
    rid=int(d[2]);stage=int(d[3]) if len(d)>3 else 1
    uid=q.from_user.id;st=B.S.setdefault(uid,{})
    if d[1]=="send":
        st.update(mode="partner_send_code",code_request_id=rid,code_stage=stage)
        await q.answer();return await q.message.reply_text(f"🔐 کد مرحله {stage} را ارسال کنید:")
    if d[1]=="next" and _admin(B,uid):
        pid=st.get("code_partner_id")
        target=_partner_uid(B,pid)
        if not target:return await q.message.reply_text("❌ همکار در دسترس نیست.")
        nxt=min(10,stage+1);st["code_stage"]=nxt
        await context.bot.send_message(target,f"🔐 مرحله {nxt} از ۱۰\nکد مرحله {nxt} را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📨 ارسال کد مرحله {nxt}",callback_data=f"code:send:{rid}:{nxt}")]]))
        return await q.message.reply_text(f"📨 مرحله {nxt} برای همکار ارسال شد.")

async def _code_text(update,context,B):
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    if st.get("mode")!="partner_send_code":return
    rid=int(st.get("code_request_id"));stage=int(st.get("code_stage",1));text=(update.message.text or "").strip()
    if not text:return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_codes(request_id INTEGER,stage INTEGER,code TEXT,created_at TEXT,PRIMARY KEY(request_id,stage))")
    B.db.conn.execute("INSERT OR REPLACE INTO request_partner_codes VALUES(?,?,?,?)",(rid,stage,text,B.now()));B.db.conn.commit()
    r=B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?",(rid,)).fetchone()
    for aid in B.ADM:
        try:
            buttons=[]
            if stage<10:buttons.append(InlineKeyboardButton(f"➡️ مرحله {stage+1}",callback_data=f"code:next:{rid}:{stage}"))
            buttons.append(InlineKeyboardButton("✅ پایان دریافت代码",callback_data=f"code:finish:{rid}:{stage}"))
            await context.bot.send_message(int(aid),f"🔐 کد همکار دریافت شد\n🎫 {r['tracking_code'] if r else rid}\nمرحله: {stage} از ۱۰\nکد: {text}",reply_markup=InlineKeyboardMarkup([buttons]))
        except Exception:pass
    st["mode"]=None
    return await update.message.reply_text(f"✅ کد مرحله {stage} دریافت و برای مدیریت ارسال شد.")

async def install(app,B):
    if getattr(B,"_request_control_installed",False):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_codes(request_id INTEGER,stage INTEGER,code TEXT,created_at TEXT,PRIMARY KEY(request_id,stage))");B.db.conn.commit()
    app.add_handler(CallbackQueryHandler(lambda u,c:_cb(u,c,B),pattern=r"^panel:"),group=-45)
    app.add_handler(CallbackQueryHandler(lambda u,c:_code_cb(u,c,B),pattern=r"^code:"),group=-44)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_code_text(u,c,B)),group=-43)
    B._request_control_installed=True
