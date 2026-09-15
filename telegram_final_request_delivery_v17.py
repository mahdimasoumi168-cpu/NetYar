"""Final request delivery guard: full details, attachments and partner tickets."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop
log=logging.getLogger("netyar.final_request_delivery")

def _full(B,rid):
    r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(int(rid),)).fetchone()
    if not r:return None,[]
    rows=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(int(rid),)).fetchall()
    lines=["📋 اطلاعات کامل درخواست",f"🎫 کد پیگیری: {r['tracking_code']}",f"🧾 خدمت: {r['service_key']}",f"📌 وضعیت: {r['status']}",f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",f"💳 پرداخت: {r['payment_status'] or '-'}"]
    files=[]
    labels={"phone":"📱 شماره موبایل مشترک","mobile":"📱 شماره موبایل مشترک","gov_phone":"📱 شماره موبایل مشترک","gov_dob":"🎂 تاریخ تولد مشترک","gov_unique":"🆔 شناسه یکتای مشترک","gov_special":"🔖 شناسه اختصاصی مشترک","gov_family_code":"👨‍👩‍👧‍👦 کد خانوار مشترک","gov_postal":"📮 کد پستی مشترک","gov_identity_number":"🪪 شماره مدرک","gov_doc_type":"🪪 نوع مدرک","passport_number":"🛂 شماره پاسپورت مشترک","partner_name":"👤 نام همکار","partner_phone":"📞 موبایل همکار","subscriber_phone":"📱 شماره موبایل مشترک","carrier":"📡 اپراتور","service":"🧾 خدمت"}
    for x in rows:
        k=str(x['field_key'] or ''); a=str(x['answer'] or '').strip(); f=str(x['file_id'] or '').strip()
        if a:lines.append(f"{labels.get(k,'📋 '+k.replace('_',' '))}: {a}")
        if f:files.append((labels.get(k,'📎 '+k.replace('_',' ')),f))
    return "\n".join(lines),files

async def _media(bot,aid,files,rid):
    for label,fid in files:
        try:
            await bot.send_photo(chat_id=int(aid),photo=fid,caption=f"{label}\n🎫 درخواست #{rid}")
        except Exception:
            try: await bot.send_document(chat_id=int(aid),document=fid,caption=f"{label}\n🎫 درخواست #{rid}")
            except Exception: log.exception("attachment delivery failed rid=%s label=%s",rid,label)

def install(app,B):
    if getattr(B,"_final_request_delivery_v17",False):return
    async def admin_detail(update,context):
        q=update.callback_query
        if not q:return
        data=str(q.data or '')
        if not (data.startswith('panel:req:') or data.startswith('panel:resend:')):return
        if not B.admin(q.from_user.id):return
        try:rid=int(data.rsplit(':',1)[1])
        except Exception:return
        text,files=_full(B,rid)
        if not text:
            await q.answer('❌ درخواست پیدا نشد.',show_alert=True);raise ApplicationHandlerStop
        mk=InlineKeyboardMarkup([[InlineKeyboardButton('⏳ در حال بررسی',callback_data=f'panel:review:{rid}'),InlineKeyboardButton('✅ انجام شد',callback_data=f'panel:approve:{rid}')],[InlineKeyboardButton('❌ رد درخواست',callback_data=f'panel:reject:{rid}')],[InlineKeyboardButton('⬅️ پنل مدیریت',callback_data='adm:menu')]])
        await q.message.reply_text(text,reply_markup=mk)
        await _media(context.bot,q.from_user.id,files,rid)
        await q.answer('✅ اطلاعات و مدارک ارسال شد.')
        raise ApplicationHandlerStop
    async def ticket(update,context):
        q=update.callback_query
        if not q:return
        data=str(q.data or '')
        if not data.startswith('pr:self:ticket:'):return
        rid=int(data.rsplit(':',1)[1]); st=B.S.setdefault(q.from_user.id,{})
        row=B.db.conn.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        if not row or int(st.get('partner_id') or -1)!=int(row['user_id']):
            await q.answer('❌ دسترسی به این درخواست ندارید.',show_alert=True);raise ApplicationHandlerStop
        text,files=_full(B,rid)
        admins=list(dict.fromkeys(getattr(B,'ADM',set()) or []))
        for aid in admins:
            try:
                await context.bot.send_message(chat_id=int(aid),text='✉️ تیکت همکار\n\n'+(text or 'درخواست بدون جزئیات'))
                await _media(context.bot,aid,files,rid)
            except Exception:log.exception('partner ticket delivery failed rid=%s',rid)
        await q.answer('✅ تیکت برای مدیریت ارسال شد.',show_alert=True)
        await q.message.reply_text('✅ تیکت همراه با اطلاعات و مدارک درخواست برای مدیریت ارسال شد.')
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(admin_detail,pattern=r'^panel:(?:req|resend):\d+$'),group=-200000)
    app.add_handler(CallbackQueryHandler(ticket,pattern=r'^pr:self:ticket:\d+$'),group=-200001)
    B._final_request_delivery_v17=True
