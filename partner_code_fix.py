"""Reliable partner verification-code bridge for NetYar."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
log = logging.getLogger('netyar.partner_code_fix')

def install():
    import bot as B
    if getattr(B, '_partner_code_fix_installed', False):
        return

    old_ptext = B.ptext
    async def ptext_bound(update, context):
        result = await old_ptext(update, context)
        try:
            uid = update.effective_user.id
            st = B.S.get(uid, {})
            pid = st.get('partner_id')
            if pid and st.get('partner_active', True):
                B.db.set_setting(f'partner_chat_{pid}', str(update.effective_chat.id))
        except Exception:
            log.exception('partner chat binding failed')
        return result
    B.ptext = ptext_bound

    old_admin_cb = B.admin_cb
    async def admin_cb_fixed(update, context):
        q = update.callback_query
        data = str(q.data or '').split(':')
        if len(data) >= 3 and data[0] == 'req' and data[1] == 'p':
            if not B.admin(q.from_user.id):
                await q.answer('دسترسی ندارید')
                return
            try:
                rid = int(data[2])
                req = B.db.conn.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
                if not req:
                    await q.answer('درخواست پیدا نشد')
                    return
                pid = None
                try:
                    cols = [r['name'] for r in B.db.conn.execute('PRAGMA table_info(requests)').fetchall()]
                    if 'partner_id' in cols:
                        rr = B.db.conn.execute('SELECT partner_id FROM requests WHERE id=?', (rid,)).fetchone()
                        pid = rr['partner_id'] if rr and rr['partner_id'] else None
                except Exception:
                    pass
                if not pid:
                    val = B.db.setting(f'request_partner_{rid}', '')
                    pid = int(val) if str(val).isdigit() else None

                candidates = B.db.conn.execute('SELECT * FROM partners WHERE active=1 ORDER BY id DESC').fetchall()
                partner = None
                for p in candidates:
                    if pid and int(p['id']) != int(pid):
                        continue
                    chat = B.db.setting(f'partner_chat_{p["id"]}', '')
                    if chat:
                        partner = p
                        break
                if partner is None and pid:
                    p = B.db.conn.execute('SELECT * FROM partners WHERE id=? AND active=1', (pid,)).fetchone()
                    if p:
                        partner = p
                if partner is None and len(candidates) == 1:
                    partner = candidates[0]
                if not partner:
                    await q.answer('همکار فعال برای این درخواست پیدا نشد', show_alert=True)
                    return
                chat = B.db.setting(f'partner_chat_{partner["id"]}', '')
                if not chat:
                    await q.answer('چت همکار ثبت نشده است؛ همکار یک‌بار وارد پنل شود.', show_alert=True)
                    return

                B.db.set_setting(f'request_partner_{rid}', str(partner['id']))
                B.db.set_setting(f'partner_code_request_{partner["id"]}', f'{rid}|{req["tracking_code"]}')
                B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code', updated_at=? WHERE id=?", (B.now(), rid))
                B.db.conn.commit()
                await context.bot.send_message(
                    chat_id=int(chat),
                    text=(f'🔐 درخواست کد تأیید\n\n'
                          f'🎫 کد پیگیری: {req["tracking_code"]}\n'
                          f'🧾 خدمت: {req["service_key"]}\n\n'
                          'لطفاً کد/رمز موردنیاز را همین‌جا ارسال کنید.\n'
                          'پس از ارسال، اطلاعات برای مدیریت فرستاده می‌شود.'),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ لغو درخواست کد', callback_data=f'pc:x:{rid}:{partner["id"]}')]])
                )
                await q.answer('درخواست کد برای همکار ارسال شد')
                await q.message.reply_text(
                    f'🔐 درخواست کد ارسال شد.\n👥 همکار: {partner["name"] or partner["phone"]}\n🎫 {req["tracking_code"]}\n⏳ منتظر پاسخ همکار هستیم.'
                )
                return
            except Exception:
                log.exception('partner code request failed')
                await q.answer('خطا در پردازش درخواست کد', show_alert=True)
                return
        return await old_admin_cb(update, context)

    B.admin_cb = admin_cb_fixed
    B._partner_code_fix_installed = True
    log.info('Partner verification-code fix installed')
