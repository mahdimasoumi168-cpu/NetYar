"""Stable Telegram request controls with complete request details."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
_SEEN=set()

def partner_uid(B,pid):
    try:
        r=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(pid,)).fetchone(); return int(r["telegram_user_id"]) if r and str(r["telegram_user_id"]).isdigit() else None
    except Exception:return None

def admin_kb(B):
    try:
        import telegram_admin_plus as A; return A._admin_menu()
    except Exception:return None

def once(q):
    cid=getattr(q,"id",None)
    if not cid:return True
    if cid in _SEEN:return False
    _SEEN.add(cid)
    if len(_SEEN)>1500:_SEEN.clear();_SEEN.add(cid)
    return True

def menu(rid,paid=False):
    rows=[[InlineKeyboardButton("🔎 جزئیات کامل",callback_data=f"rq:detail:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")]]
    rows.append([InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"rq:approve:{rid}")]) if paid else rows.extend([[InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"rq:payconfirm:{rid}")],[InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}")]])
    rows.append([InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")]); return InlineKeyboardMarkup(rows)

DETAIL_LABELS={"doc_type":"🪪 نوع مدرک","phone":"📱 شماره موبایل مشترک","mobile":"📱 شماره موبایل مشترک","customer_phone":"📱 شماره موبایل مشترک","dob":"🎂 تاریخ تولد مشترک","birth_date":"🎂 تاریخ تولد مشترک","unique_id":"🆔 شناسه یکتای مشترک","unique_code":"🆔 شناسه یکتای مشترک","special_id":"🔖 شناسه اختصاصی مشترک","special_code":"🔖 شناسه اختصاصی مشترک","family_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","household_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","postal_code":"📮 کد پستی مشترک","passport":"🛂 شماره گذرنامه مشترک","passport_number":"🛂 شماره گذرنامه مشترک","temporary_card_number":"📄 شماره کارت موقت","booklet_number":"📗 شماره دفترچه اقامت مشترک","residence_booklet_number":"📗 شماره دفترچه اقامت مشترک","document":"📸 تصویر مدرک","partner_id":"👤 شناسه همکار","name":"👤 نام مشترک","full_name":"👤 نام و نام خانوادگی مشترک","user_id":"👤 شناسه درخواست‌دهنده"}
DOC_TYPES={"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}

def detail_line(key,value): return f"{DETAIL_LABELS.get(key,key)}: {DOC_TYPES.get(str(value),value) if key=='doc_type' else value}"

def _field_label(key):
    try:
        import request_language_actions as L
        return L.field_label(key,"fa")
    except Exception:
        return DETAIL_LABELS.get(key,f"📋 {key}")

def _service_name(B,key):
    try:
        import request_language_actions as L
        return L.service_name(key,"fa")
    except Exception:return str(key or "-")

async def _send_attachment(q,fid,caption):
    try:
        await q.message.reply_photo(photo=fid,caption=caption)
        return
    except Exception: pass
    try:
        await q.message.reply_document(document=fid,caption=caption)
    except Exception: pass

async def cb(update,context,B):
    q=update.callback_query
    if not q:return
    d=(q.data or "").split(":")
    if len(d)<3 or d[0]!="rq":return
    if not once(q):
        try:await q.answer()
        except Exception:pass
        return
    if not B.admin(q.from_user.id):await q.answer("دسترسی ندارید",show_alert=True);return
    await q.answer();rid=int(d[2]);r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
    if not r:return await q.message.reply_text("❌ درخواست پیدا نشد.",reply_markup=admin_kb(B))
    action=d[1];paid=str(r["payment_status"] or "").lower()=="paid"
    if action=="detail":
        # Build details from BOTH the requests row and every request_answers row.
        # This guarantees that mobile, DOB, unique ID and special ID are shown
        # even when a service stores them only in request_answers.
        ans=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
        lines=["🔎 جزئیات کامل درخواست","",f"🎫 کد پیگیری: {r['tracking_code']}",f"🧾 خدمت: {_service_name(B,r['service_key'])}",f"📌 وضعیت: {r['status']}",f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",f"💳 پرداخت: {'تأیید شده' if paid else 'تأیید نشده'}"]
        if r["payment_method"]: lines.append(f"💵 روش پرداخت: {r['payment_method']}")
        if r["created_at"]: lines.append(f"🕐 زمان ثبت: {r['created_at']}")
        # First show important identity fields in a predictable order.
        important=("phone","mobile","customer_phone","dob","birth_date","unique_id","unique_code","special_id","special_code","family_code","household_code","postal_code","passport","passport_number","booklet_number","residence_booklet_number","doc_type","name","full_name")
        seen=set()
        for key in important:
            for a in ans:
                if str(a["field_key"])!=key or not str(a["answer"] or "").strip() or key in seen: continue
                lines.append(detail_line(key,str(a["answer"]).strip()));seen.add(key)
                break
        # Include every populated requests-table field as well.
        for key in r.keys():
            if key in {"id","tracking_code","service_key","status","amount","payment_status","payment_method","created_at","updated_at","language","user_id"}: continue
            value=str(r[key] or "").strip()
            if value and key not in seen:
                lines.append(f"{_field_label(key)}: {value}");seen.add(key)
        lines.append("")
        lines.append("📋 سایر اطلاعات و پاسخ‌های ثبت‌شده:")
        visible=0
        for a in ans:
            key=str(a["field_key"]); value=str(a["answer"] or "").strip(); fid=a["file_id"]
            if not value and not fid: continue
            if value and key not in seen:
                lines.append(f"{_field_label(key)}: {value}")
            elif value and key in seen:
                # Still include duplicate answers if the same field was submitted more than once.
                lines.append(f"{_field_label(key)}: {value}")
            if fid: lines.append(f"{_field_label(key)}: 📎 فایل پیوست دارد")
            visible+=1
        if not visible: lines.append("-")
        await q.message.reply_text("\n".join(lines),reply_markup=menu(rid,paid))
        # Send every attachment belonging to this request after the text details.
        for a in ans:
            fid=a["file_id"]
            if fid: await _send_attachment(q,fid,_field_label(str(a["field_key"])))
        return
    if action=="payconfirm":
        if paid:return await q.message.reply_text("ℹ️ پرداخت قبلاً تأیید شده است.",reply_markup=admin_kb(B))
        B.db.conn.execute("UPDATE requests SET payment_status='paid',payment_method='card_to_card_manual',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit();return await q.message.reply_text("✅ دریافت وجه تأیید شد و درخواست آماده انجام خدمت است.",reply_markup=admin_kb(B))
    if action in {"review","approve","reject"}:
        if action=="approve" and not paid:return await q.message.reply_text("⛔ ابتدا دریافت وجه را تأیید کنید.",reply_markup=admin_kb(B))
        status="rejected" if action=="reject" else ("reviewing" if action=="review" else "completed");B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid));B.db.conn.commit();return await q.message.reply_text({"review":"⏳ درخواست وارد بررسی اولیه شد.","approve":"✅ درخواست انجام شد و پرونده بسته شد.","reject":"❌ درخواست رد شد و پرونده بسته شد."}[action],reply_markup=admin_kb(B))
    if action=="ask":
        pid=r["user_id"];target=partner_uid(B,pid)
        if not target:return await q.message.reply_text("❌ تلگرام همکار برای این درخواست متصل نیست.",reply_markup=admin_kb(B))
        st=B.S.setdefault(q.from_user.id,{});st.update(code_request_id=rid,code_partner_id=pid,code_stage=1);await context.bot.send_message(target,f"🔐 درخواست کد مدیریت\n🎫 {r['tracking_code']}\n\nمرحله ۱ از ۱۰\nکد مرحله ۱ را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📨 ارسال کد مرحله ۱",callback_data=f"rqcode:send:{rid}:1")]]));return await q.message.reply_text("📨 مرحله ۱ برای همکار ارسال شد.\nپس از پایان، پرونده به پنل مدیریت برمی‌گردد.",reply_markup=admin_kb(B))

async def code_cb(update,context,B):
    q=update.callback_query
    if not q:return
    d=(q.data or "").split(":")
    if len(d)<4 or d[0]!="rqcode":return
    if not once(q):
        try:await q.answer()
        except Exception:pass
        return
    rid=int(d[2]);stage=int(d[3]);uid=q.from_user.id;st=B.S.setdefault(uid,{})
    if d[1]=="send":
        r=B.db.conn.execute("SELECT user_id FROM requests WHERE id=?",(rid,)).fetchone()
        if not r or str(st.get("partner_id"))!=str(r["user_id"]):return await q.answer("این درخواست متعلق به شما نیست.",show_alert=True)
        st.update(mode="partner_send_code",code_request_id=rid,code_stage=stage);await q.answer();return await q.message.reply_text(f"🔐 کد مرحله {stage} را همینجا ارسال کنید:")
    if d[1]=="next" and B.admin(uid):
        pid=st.get("code_partner_id");target=partner_uid(B,pid);nxt=stage+1
        if not target:return await q.message.reply_text("❌ همکار در دسترس نیست.",reply_markup=admin_kb(B))
        if nxt>10:return await q.message.reply_text("✅ هر ۱۰ مرحله تکمیل شده است.",reply_markup=admin_kb(B))
        st["code_stage"]=nxt;await context.bot.send_message(target,f"🔐 مرحله {nxt} از ۱۰\nکد مرحله {nxt} را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📨 ارسال کد مرحله {nxt}",callback_data=f"rqcode:send:{rid}:{nxt}")]]));return await q.message.reply_text(f"📨 مرحله {nxt} ارسال شد.")
    if d[1]=="finish" and B.admin(uid):
        st["code_request_id"]=None;st["code_partner_id"]=None;st["code_stage"]=None;st["mode"]=None;return await q.message.reply_text("✅ دریافت کدها پایان یافت. پرونده بسته شد.",reply_markup=admin_kb(B))

async def code_text(update,context,B):
    if not update.message:return
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    if st.get("mode")!="partner_send_code":return
    rid=int(st.get("code_request_id"));stage=int(st.get("code_stage",1));text=(update.message.text or "").strip();r=B.db.conn.execute("SELECT user_id,tracking_code FROM requests WHERE id=?",(rid,)).fetchone()
    if not r or str(st.get("partner_id"))!=str(r["user_id"]):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_codes(request_id INTEGER,stage INTEGER,code TEXT,created_at TEXT,PRIMARY KEY(request_id,stage))");B.db.conn.execute("INSERT OR REPLACE INTO request_partner_codes VALUES(?,?,?,?)",(rid,stage,text,B.now()));B.db.conn.commit()
    for aid in B.ADM:
        try:
            buttons=[]
            if stage<10:buttons.append(InlineKeyboardButton(f"➡️ مرحله {stage+1}",callback_data=f"rqcode:next:{rid}:{stage}"))
            buttons.append(InlineKeyboardButton("✅ پایان",callback_data=f"rqcode:finish:{rid}:{stage}"));await context.bot.send_message(int(aid),f"🔐 کد همکار دریافت شد\n🎫 {r['tracking_code']}\nمرحله {stage} از ۱۰\nکد: {text}",reply_markup=InlineKeyboardMarkup([buttons]))
        except Exception:pass
    st["mode"]=None;await update.message.reply_text(f"✅ کد مرحله {stage} برای مدیریت ارسال شد.")

def install(app,B):
    if getattr(B,"_request_control_v2",False):return
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_codes(request_id INTEGER,stage INTEGER,code TEXT,created_at TEXT,PRIMARY KEY(request_id,stage))");B.db.conn.commit();app.add_handler(CallbackQueryHandler(lambda u,c:cb(u,c,B),pattern=r"^rq:"),group=-50);app.add_handler(CallbackQueryHandler(lambda u,c:code_cb(u,c,B),pattern=r"^rqcode:"),group=-49);app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:code_text(u,c,B)),group=-48);B._request_control_v2=True
