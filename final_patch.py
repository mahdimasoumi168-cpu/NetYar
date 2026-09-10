# NetYar final compatibility patch
import asyncio, logging
log=logging.getLogger('netyar.final_patch')

def _style(text):
    t=str(text)
    if any(x in t for x in ('تأیید','فعال','شارژ','ذخیره','success','Approve','ثبت')): return 'success'
    if any(x in t for x in ('رد','حذف','لغو','انصراف','danger','Reject','Cancel')): return 'danger'
    return 'primary'

def _btn(cls,text,**kwargs):
    style=_style(text)
    try: return cls(str(text),api_kwargs={'style':style},**kwargs)
    except Exception:
        try: return cls(str(text),**kwargs)
        except Exception: return str(text)

def install():
    import bot as B
    from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
    def colored_kb(rows):
        return ReplyKeyboardMarkup([[_btn(KeyboardButton,text) for text in (row or [])] for row in (rows or [])], resize_keyboard=True)
    B.kb=colored_kb

    async def statuscb(u,c):
        q=u.callback_query; await q.answer(); uid=q.from_user.id; B.S.setdefault(uid,{})['status']=q.data.split(':')[1]
        if B.S[uid]['status']!='foreign': return await q.message.reply_text('🇮🇷 خدمات ایرانی فعلاً فعال نیست.', reply_markup=B.main(uid))
        text=('📋 منوی خدمات «کمک یار مهاجر»\n\n'
              '1️⃣ 🪪 فیدای غیر حضوری\n2️⃣ 🖨 خدمات چاپ\n3️⃣ 🏛 حل مشکل ورود اتباع دولت من\n4️⃣ 🎫 کد رهگیری تمدید کارت‌ها\n5️⃣ 📱 خدمات سیم‌کارت\n6️⃣ 📝 آزمون غربالگری\n7️⃣ 🎫 پیگیری\n8️⃣ 💰 کیف پول من\n9️⃣ 📞 تماس با ما\n🔟 📝 ثبت شکایت مشتریان\n👥 پنل همکاران\n\nلطفاً گزینه موردنظر را انتخاب کنید.')
        return await q.message.reply_text(text, reply_markup=B.main(uid))
    B.statuscb=statuscb

    async def notify_admins(app,message,request_id=None,inline=None):
        if not B.ADM:return
        mk=inline
        if request_id and mk is None:
            mk=InlineKeyboardMarkup([[_btn(InlineKeyboardButton,'🔎 مشاهده درخواست',callback_data=f'req:v:{request_id}')],[_btn(InlineKeyboardButton,'✅ تأیید خدمت',callback_data=f'req:a:{request_id}'),_btn(InlineKeyboardButton,'❌ رد خدمت',callback_data=f'req:x:{request_id}')],[_btn(InlineKeyboardButton,'🔐 درخواست کد از همکار',callback_data=f'req:p:{request_id}')],[_btn(InlineKeyboardButton,'✉️ پاسخ',callback_data=f'req:r:{request_id}')]])
        for aid in B.ADM:
            try:
                await app.bot.send_message(chat_id=int(aid),text=message,reply_markup=mk)
                if request_id:
                    rows=B.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id IS NOT NULL AND file_id!='' ORDER BY id",(request_id,)).fetchall()
                    for r in rows:
                        try: await app.bot.send_photo(chat_id=int(aid),photo=r['file_id'],caption=f'📎 فایل درخواست #{request_id}')
                        except Exception:
                            try: await app.bot.send_document(chat_id=int(aid),document=r['file_id'],caption=f'📎 فایل درخواست #{request_id}')
                            except Exception: log.exception('admin file send failed')
            except Exception: log.exception('admin notification failed')
    B.notify_admins=notify_admins

    _old_ptext=B.ptext
    async def ptext(u,c):
        uid=u.effective_user.id; st=B.S.setdefault(uid,{}); t=(u.message.text or '').strip(); pid=st.get('partner_id'); pending=B.db.setting(f'partner_code_request_{pid}','') if pid else ''
        if pid and pending and t not in {B.CANCEL,'لغو','❌ لغو'}:
            rid=int(pending); B.db.answer(rid,'verification_code',answer=t); B.db.set_setting(f'partner_code_request_{pid}',''); B.db.conn.commit()
            for aid in B.ADM:
                try:
                    mk=InlineKeyboardMarkup([[_btn(InlineKeyboardButton,'🔎 مشاهده',callback_data=f'req:v:{rid}'),_btn(InlineKeyboardButton,'✅ تأیید',callback_data=f'req:a:{rid}'),_btn(InlineKeyboardButton,'❌ رد',callback_data=f'req:x:{rid}')]])
                    await c.bot.send_message(chat_id=int(aid),text=f'🔐 کد تأیید همکار دریافت شد.\n🎫 درخواست #{rid}\n👥 همکار: {pid}\n🔑 کد: {t}',reply_markup=mk)
                except Exception: log.exception('verification admin notification failed')
            return await u.message.reply_text('✅ کد تأیید دریافت شد و برای مدیریت ارسال شد.',reply_markup=B.partner_kb())
        result=await _old_ptext(u,c)
        if st.get('partner_id') and st.get('mode') is None: B.db.set_setting(f'partner_chat_{st["partner_id"]}',str(uid))
        return result
    B.ptext=ptext

    _old_admin_cb=B.admin_cb
    async def admin_cb(u,c):
        q=u.callback_query; data=(q.data or '').split(':')
        if len(data)>=3 and data[0]=='req' and B.admin(q.from_user.id):
            rid=int(data[2]); r=B.db.conn.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if not r: await q.answer('درخواست پیدا نشد'); return
            if data[1] in {'a','x'}:
                await q.answer(); status='approved' if data[1]=='a' else 'rejected'; B.db.conn.execute('UPDATE requests SET status=?,updated_at=? WHERE id=?',(status,B.now(),rid)); B.db.conn.commit()
                row=B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(rid,)).fetchone(); pid=str(row['answer']) if row else ''; chat=B.db.setting(f'partner_chat_{pid}','') if pid else ''
                if chat:
                    try: await c.bot.send_message(chat_id=int(chat),text=('✅ خدمت شما توسط مدیریت تأیید شد.' if status=='approved' else '❌ خدمت شما توسط مدیریت رد شد.'),reply_markup=B.partner_kb())
                    except Exception: pass
                await q.message.edit_reply_markup(reply_markup=None); return await q.message.reply_text(('✅ خدمت تأیید شد و نتیجه ارسال شد.' if status=='approved' else '❌ خدمت رد شد و نتیجه ارسال شد.'),reply_markup=B.amenu())
            if data[1]=='p':
                await q.answer(); row=B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(rid,)).fetchone(); pid=str(row['answer']) if row else ''
                if not pid: return await q.message.reply_text('⚠️ این درخواست به همکار متصل نیست.',reply_markup=B.amenu())
                chat=B.db.setting(f'partner_chat_{pid}','')
                if not chat: return await q.message.reply_text('⚠️ همکار هنوز اتصال چت خود را ثبت نکرده است.',reply_markup=B.amenu())
                B.db.set_setting(f'partner_code_request_{pid}',str(rid))
                try: await c.bot.send_message(chat_id=int(chat),text=f'🔐 مدیریت برای درخواست {r["tracking_code"]} کد تأیید می‌خواهد.\nفقط کد تأیید همان خدمت را بفرستید؛ رمز ورود پنل را ارسال نکنید.',reply_markup=B.partner_kb())
                except Exception: log.exception('partner code request send failed')
                return await q.message.reply_text('✅ درخواست کد برای همکار ارسال شد.',reply_markup=B.amenu())
        return await _old_admin_cb(u,c)
    B.admin_cb=admin_cb

    _old_router=B.router
    async def router(u,c):
        t=(u.message.text or '').strip(); uid=u.effective_user.id; st=B.S.setdefault(uid,{})
        nums={'1️⃣':'🪪 فیدای غیر حضوری','2️⃣':'🖨 خدمات چاپ','3️⃣':'🪪 حل مشکل ورود اتباع دولت من','4️⃣':'🎫 کد رهگیری تمدید کارت‌ها','5️⃣':'📱 خدمات سیم کارت','6️⃣':'📝 آزمون غربالگری','7️⃣':'🎫 پیگیری','8️⃣':'💰 کیف پول من','9️⃣':'📞 تماس با ما','🔟':'📝 ثبت شکایت مشتریان'}
        if st.get('status')=='foreign' and st.get('mode') is None and t[:2] in nums: u.message.text=nums[t[:2]]
        return await _old_router(u,c)
    B.router=router

    try:
        import server
        async def watchdog_without_rubika_registration():
            while True:
                try:
                    await asyncio.sleep(90)
                    if server.telegram_app is not None:
                        try:
                            info=await server.telegram_app.bot.get_webhook_info(); expected=server.public_url('/telegram/update')
                            if (info.url or '').rstrip('/')!=expected.rstrip('/'): await server.telegram_app.bot.set_webhook(url=expected,allowed_updates=None)
                            server.telegram_ready=True
                        except Exception: server.telegram_ready=False
                except asyncio.CancelledError: return
                except Exception: log.exception('integration watchdog failed')
        server._integration_watchdog=watchdog_without_rubika_registration
    except Exception: log.exception('server patch failed')

install()
