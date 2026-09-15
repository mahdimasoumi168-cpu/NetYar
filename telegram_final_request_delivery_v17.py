"""Final request delivery guard: full details, attachments and admin options."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop
log=logging.getLogger("netyar.final_request_delivery")

def _full(B,rid):
    r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(int(rid),)).fetchone()
    if not r:return None,[]
    rows=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(int(rid),)).fetchall()
    labels={"phone":"📱 شماره موبایل مشترک","mobile":"📱 شماره موبایل مشترک","gov_phone":"📱 شماره موبایل مشترک","dob":"🎂 تاریخ تولد مشترک","gov_dob":"🎂 تاریخ تولد مشترک","unique_id":"🆔 شناسه یکتای مشترک","gov_unique":"🆔 شناسه یکتای مشترک","special_id":"🔖 شناسه اختصاصی مشترک","gov_special":"🔖 شناسه اختصاصی مشترک","family_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","gov_family_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","postal_code":"📮 کد پستی مشترک","gov_postal":"📮 کد پستی مشترک","passport_number":"🛂 شماره پاسپورت مشترک","booklet_number":"📗 شماره دفترچه اقامت مشترک","partner_id":"👤 شناسه همکار","doc_type":"🪪 نوع مدرک","carrier":"📡 اپراتور","service":"🧾 خدمت"}
    lines=["📋 اطلاعات کامل درخواست",f"🎫 کد پیگیری: {r['tracking_code']}",f"🧾 خدمت: {r['service_key']}",f"📌 وضعیت: {r['status']}",f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",f"💳 پرداخت: {r['payment_status'] or '-'}"]
    files=[]
    for x in rows:
        k=str(x['field_key'] or '');a=str(x['answer'] or '').strip();f=str(x['file_id'] or '').strip()
        if a:lines.append(f"{labels.get(k,'📋 '+k.replace('_',' '))}: {a}")
        if f:files.append((labels.get(k,'📎 '+k.replace('_',' ')),f))
    return "\n".join(lines),files

async def _media(bot,aid,files,rid):
    for label,fid in files:
        delivered=False
        for kind in ("photo","document"):
            try:
                if kind=="photo": await bot.send_photo(chat_id=int(aid),photo=fid,caption=f"{label}\n🎫 درخواست #{rid}")
                else: await bot.send_document(chat_id=int(aid),document=fid,caption=f"{label}\n🎫 درخواست #{rid}")
                delivered=True;break
            except Exception: continue
        if not delivered: log.exception("attachment delivery failed rid=%s label=%s",rid,label)

def _mk(rid,paid=False):
    rows=[[InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"panel:req:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")]]
    if paid: rows.append([InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"rq:approve:{rid}")])
    else: rows.append([InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"rq:payconfirm:{rid}"),InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}")])
    rows.append([InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")]);return InlineKeyboardMarkup(rows)

def install(app,B):
    if getattr(B,"_final_request_delivery_v18",False):return
    async def admin_detail(update,context):
        q=update.callback_query
        if not q:return
        data=str(q.data or '')
        if not (data.startswith('panel:req:') or data.startswith('panel:resend:')):return
        if not B.admin(q.from_user.id):return
        try:rid=int(data.rsplit(':',1)[1])
        except Exception:return
        text,files=_full(B,rid)
        if not text: await q.answer('❌ درخواست پیدا نشد.',show_alert=True);raise ApplicationHandlerStop
        r=B.db.conn.execute("SELECT payment_status FROM requests WHERE id=?",(rid,)).fetchone();paid=bool(r and str(r['payment_status'] or '').lower()=='paid')
        await q.message.reply_text(text,reply_markup=_mk(rid,paid));await _media(context.bot,q.from_user.id,files,rid);await q.answer('✅ اطلاعات، مدارک و گزینه‌های مدیریتی ارسال شد.');raise ApplicationHandlerStop
    async def ticket_entry(update,context):
        q=update.callback_query
        if not q or not str(q.data or '').startswith('pr:self:ticket:'):return
        st=B.S.setdefault(q.from_user.id,{})
        if not st.get('partner_id'): await q.answer('❌ ابتدا وارد پنل همکاران شوید.',show_alert=True);raise ApplicationHandlerStop
        try:rid=int(q.data.rsplit(':',1)[1])
        except Exception: await q.answer('❌ درخواست نامعتبر است.',show_alert=True);raise ApplicationHandlerStop
        row=B.db.conn.execute('SELECT user_id FROM requests WHERE id=?',(rid,)).fetchone()
        if not row or str(row['user_id'])!=str(st.get('partner_id')): await q.answer('❌ این درخواست متعلق به شما نیست.',show_alert=True);raise ApplicationHandlerStop
        st['mode']='ticket_partner_reply';st['ticket_request_id']=rid;await q.answer();await q.message.reply_text('✉️ تیکت به مدیریت\n\nپاسخ یا توضیح خود را ارسال کنید. متن، عکس، ویدیو، ویس یا فایل قابل ارسال است.',reply_markup=B.cancel_kb(st.get('lang','fa')));raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(admin_detail,pattern=r'^panel:(?:req|resend):\d+$'),group=-200000)
    app.add_handler(CallbackQueryHandler(ticket_entry,pattern=r'^pr:self:ticket:\d+$'),group=-200001)
    B._final_request_delivery_v18=True
    B._final_request_delivery_v17=True
