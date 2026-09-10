import logging
log=logging.getLogger('netyar.rubika_admin_patch')

def install():
    import rubika_v2 as R
    import server
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    try: import bot as B
    except Exception: B=None
    def btn(text,data,style=None):
        try: return InlineKeyboardButton(text,callback_data=data,api_kwargs={'style':style or ('success' if 'تأیید' in text else 'danger' if 'رد' in text else 'primary')})
        except Exception: return InlineKeyboardButton(text,callback_data=data)
    async def notify_telegram(rid,code,key,amount,partner_id=None):
        app=getattr(server,'telegram_app',None)
        if app is None:return
        rows=[f"• {r['field_key']}: {r['answer'] or '📎 فایل'}" for r in R.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall() if r['answer'] or r['file_id']]
        text=f"🆕 درخواست جدید روبیکا\n🎫 کد پیگیری: {code}\n🧩 خدمت: {key}\n💰 مبلغ: {amount:,} تومان\n"+(f"👥 همکار: {partner_id}\n" if partner_id else '')+("\n".join(rows) if rows else '📎 اطلاعات تکمیلی ثبت نشده است.')
        mk=InlineKeyboardMarkup([[btn('🔎 مشاهده درخواست',f'req:v:{rid}')],[btn('✅ تأیید خدمت',f'req:a:{rid}','success'),btn('❌ رد خدمت',f'req:x:{rid}','danger')],[btn('🔐 درخواست کد از همکار',f'req:p:{rid}')],[btn('✉️ پاسخ',f'req:r:{rid}')]])
        for aid in (B.ADM if B else []):
            try:
                await app.bot.send_message(chat_id=int(aid),text=text,reply_markup=mk)
                for r in R.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",(rid,)).fetchall():
                    try: await app.bot.send_photo(chat_id=int(aid),photo=r['file_id'],caption=f'📎 فایل درخواست {code}')
                    except Exception:
                        try: await app.bot.send_document(chat_id=int(aid),document=r['file_id'],caption=f'📎 فایل درخواست {code}')
                        except Exception: log.exception('rubika admin file send failed')
            except Exception: log.exception('rubika telegram admin notification failed')
    def request(uid,chat,key,amount):
        st=R.STATE[str(uid)]; pid=st.get('partner_id')
        if pid:
            p=R.db.conn.execute('SELECT balance FROM partners WHERE id=? AND active=1',(pid,)).fetchone()
            if not p or int(p['balance'])<amount:return R.send(chat,R.T(uid,'need_balance'),R.partner_rows())
            R.db.conn.execute('UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?',(amount,R.now(),pid));R.db.conn.commit()
        user=R.db.user('rubika',uid,'',uid);rid,code=R.db.create_request(user,key,'rubika',amount);st['request_id']=rid
        if pid:R.db.answer(rid,'partner_id',str(pid))
        for i,fid in enumerate(st.get('files') or [],1):R.db.answer(rid,f'file_{i}',file_id=fid)
        if st.get('fida_doc'):R.db.answer(rid,'document',file_id=st['fida_doc'])
        R.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',updated_at=? WHERE id=?",(R.now(),rid));R.db.conn.commit();R.db.audit('rubika',uid,'create_request',code,key)
        R.send(chat,R.T(uid,'payment',code=code,amount=amount),R.partner_rows() if pid else R.main_rows(uid));R.notify_admins(f"🔔 درخواست جدید\n🎫 {code}\n🧩 {key}\n💰 {amount:,} تومان")
        import asyncio;asyncio.create_task(notify_telegram(rid,code,key,amount,pid))
    R.request=request;R._NETYAR_RUBIKA_ADMIN_PATCHED=True
install()
