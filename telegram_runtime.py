import os
import bot as B


def advanced_amenu():
    return B.kb([['👥 همکاران','➕ افزودن همکار'],['💰 شارژها','💳 پرداخت‌های مشتری'],['📋 درخواست‌ها','⚙️ قیمت‌ها'],['📊 گزارش','🤖 افزودن بات'],['🤖 بات‌های متصل','📣 اعلان خدمت'],['⬅️ منوی اصلی']])


def platform_kb():
    return B.kb([['🤖 Telegram','🤖 Rubika'],['🤖 Bale','🤖 Eitaa'],['⬅️ بازگشت']])


B.amenu = advanced_amenu
_original_main = B.main
_original_router = B.router


def split_main(uid):
    markup = _original_main(uid)
    try:
        lang = B.S.get(uid, {}).get('lang', 'fa')
        screening = {'fa': '📝 آزمون غربالگری', 'en': '📝 Screening test', 'ar': '📝 اختبار الفحص'}[lang]
        follow = {'fa': '🎫 پیگیری', 'en': '🎫 Follow-up', 'ar': '🎫 متابعة'}[lang]
        old = {'fa': '📝 آزمون غربالگری و پیگیری', 'en': '📝 Screening & follow-up', 'ar': '📝 الفحص والمتابعة'}[lang]
        rows = []
        for row in markup.keyboard:
            if old in row:
                nr = []
                for item in row:
                    if item == old:
                        nr.extend([screening, follow])
                    else:
                        nr.append(item)
                rows.append(nr)
            else:
                rows.append(list(row))
        return B.kb(rows)
    except Exception:
        return markup


B.main = split_main


async def split_router(u, c):
    t = (u.message.text or '').strip()
    uid = u.effective_user.id
    st = B.S.get(uid, {})
    lang = st.get('lang', 'fa')
    screening = {'fa': '📝 آزمون غربالگری', 'en': '📝 Screening test', 'ar': '📝 اختبار الفحص'}[lang]
    follow = {'fa': '🎫 پیگیری', 'en': '🎫 Follow-up', 'ar': '🎫 متابعة'}[lang]
    old = {'fa': '📝 آزمون غربالگری و پیگیری', 'en': '📝 Screening & follow-up', 'ar': '📝 الفحص والمتابعة'}[lang]
    track = {'fa': '🎫 کد رهگیری تمدید کارت‌ها', 'en': '🎫 Track request', 'ar': '🎫 متابعة الطلب'}[lang]

    # Run compatibility/admin/service state handlers exactly once, before the
    # original router. The previous group-1 handler caused double-processing
    # of admin buttons and stateful text input.
    result = await extra_text(u, c)
    if result is not None:
        return result

    if t == screening:
        old_text = u.message.text
        try:
            u.message.text = old
            return await _original_router(u, c)
        finally:
            u.message.text = old_text
    if t == follow:
        old_text = u.message.text
        try:
            u.message.text = track
            return await _original_router(u, c)
        finally:
            u.message.text = old_text
    return await _original_router(u, c)


B.router = split_router


async def fixed_history(u, c):
    uid = u.effective_user.id
    st = B.S.get(uid, {})
    if not st.get('partner_id'):
        return await u.message.reply_text(B.L(uid, 'ابتدا وارد پنل همکاران شوید.', 'Please log in to the partner panel first.', 'يرجى تسجيل الدخول إلى لوحة الشركاء أولاً.'), reply_markup=B.main(uid))
    rows = B.db.conn.execute('SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20', (st['partner_id'],)).fetchall()
    text = '\n'.join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,}" for r in rows) or 'سابقه‌ای نیست.'
    return await u.message.reply_text(text, reply_markup=B.partner_kb(st.get('lang', 'fa')))


B.phistory = fixed_history


async def extra_text(u, c):
    uid = u.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get('partner_id'):
        try:
            B.db.set_setting(f"partner_chat_{st['partner_id']}", str(u.effective_chat.id))
        except Exception:
            pass
    t = (u.message.text or '').strip()
    lang = st.get('lang', 'fa')

    partner_actions = {
        '➕ Top up': 'topup', '➕ شحن الحساب': 'topup', '➕ شارژ حساب': 'topup',
        '🪪 Partner request': 'gov', '🪪 طلب الشريك': 'gov', '🪪 ثبت درخواست همکار': 'gov',
        '🔎 Track code': 'track', '🔎 رمز المتابعة': 'track', '🔎 پیگیری کد': 'track',
        '📋 History': 'history', '📋 السجل': 'history', '📋 سوابق': 'history',
        '💰 Balance': 'balance', '💰 الرصيد': 'balance', '💰 موجودی': 'balance',
        '🏛 حل مشکل سامانه دولت من': 'gov'
    }
    if st.get('partner_id') and t in partner_actions:
        a = partner_actions[t]
        if a == 'topup':
            return await B.topup(u, c)
        if a == 'track':
            return await B.ptrack(u, c)
        if a == 'history':
            return await fixed_history(u, c)
        if a == 'gov':
            return await B.gov(u, c)
        if a == 'balance':
            p = B.db.conn.execute('SELECT balance FROM partners WHERE id=?', (st['partner_id'],)).fetchone()
            amount = f"{p['balance']:,}" if p else '0'
            return await u.message.reply_text({'fa': f'💰 موجودی کیف پول شما: {amount} تومان', 'en': f'💰 Your balance: {amount} toman', 'ar': f'💰 رصيدك: {amount} تومان'}[lang], reply_markup=B.partner_kb(lang))

    if st.get('mode') == 'print_color':
        if t in ('⚫ سیاه و سفید', '⚫ Black & White', '⚫ أبيض وأسود'):
            st['color'] = 'bw'
        elif t in ('🌈 رنگی', '🌈 Color', '🌈 ملون'):
            st['color'] = 'color'
        else:
            return None
        st['mode'] = 'print_side'
        return await u.message.reply_text(B.L(uid, '📄 یک‌رو یا 🔄 پشت‌ورو؟', '📄 Single-sided or 🔄 double-sided?', '📄 وجه واحد أم 🔄 وجهان؟'), reply_markup=B.kb([[B.L(uid, '📄 یک‌رو', '📄 Single-sided', '📄 وجه واحد'), B.L(uid, '🔄 پشت‌ورو', '🔄 Double-sided', '🔄 وجهان')], [B.L(uid, B.CANCEL, '❌ Cancel', '❌ إلغاء')]]))

    if st.get('mode') == 'print_side':
        if t in ('📄 یک‌رو', '📄 Single-sided', '📄 وجه واحد'):
            st['side'] = 1
        elif t in ('🔄 پشت‌ورو', '🔄 Double-sided', '🔄 وجهان'):
            st['side'] = 2
        else:
            return None
        st['mode'] = 'print_copies'
        return await u.message.reply_text(B.L(uid, '🔢 تعداد نسخه موردنیاز از هر صفحه را وارد کنید.', '🔢 Enter the number of copies per page.', '🔢 أدخل عدد النسخ لكل صفحة.'), reply_markup=B.cancel_kb(lang))

    if st.get('mode') == 'print' and t in ('✅ تأیید', '✅ Confirm', '✅ تأكيد'):
        old = u.message.text
        try:
            u.message.text = B.OK
            return await B.service_text(u, c)
        finally:
            try:
                u.message.text = old
            except Exception:
                pass

    if not B.admin(uid):
        return None

    step = st.get('extra_step')
    if t == '➕ افزودن همکار':
        st['extra_step'] = 'partner'
        return await u.message.reply_text('شماره، رمز و نام همکار را با فاصله بفرستید.\nمثال: 09991234567 123456 علی', reply_markup=B.amenu())
    if step == 'partner':
        a = t.split(maxsplit=2)
        if len(a) < 3:
            return await u.message.reply_text('❌ قالب نادرست است. مثال: 09991234567 123456 علی', reply_markup=B.amenu())
        try:
            B.db.add_partner(a[0], a[1], a[2])
            st['extra_step'] = None
            return await u.message.reply_text('✅ همکار با موفقیت اضافه شد.', reply_markup=B.amenu())
        except Exception:
            return await u.message.reply_text('❌ ثبت همکار انجام نشد؛ احتمالاً شماره تکراری است.', reply_markup=B.amenu())

    if t == '🤖 افزودن بات':
        st['extra_step'] = 'bot_platform'
        return await u.message.reply_text('پیام‌رسان را انتخاب کنید یا نام آن را متنی ارسال کنید:', reply_markup=platform_kb())
    if step == 'bot_platform':
        raw = t.lower().strip()
        aliases = {'🤖 telegram': 'telegram', '🤖 rubika': 'rubika', '🤖 bale': 'bale', '🤖 eitaa': 'eitaa', 'تلگرام': 'telegram', 'روبیکا': 'rubika', 'بله': 'bale', 'ایتا': 'eitaa'}
        p = aliases.get(raw, raw)
        if p not in {'telegram', 'rubika', 'bale', 'eitaa'}:
            return await u.message.reply_text('❌ یکی از Telegram / Rubika / Bale / Eitaa را انتخاب کنید.', reply_markup=platform_kb())
        st['bot_platform'] = p
        st['extra_step'] = 'bot_token'
        return await u.message.reply_text('🔑 API Token بات را ارسال کنید.', reply_markup=B.amenu())
    if step == 'bot_token':
        if not t:
            return await u.message.reply_text('❌ API Token خالی است. دوباره ارسال کنید.', reply_markup=B.amenu())
        st['bot_token'] = t
        st['extra_step'] = 'bot_name'
        return await u.message.reply_text('🤖 نام بات را ارسال کنید.', reply_markup=B.amenu())
    if step == 'bot_name':
        if not t:
            return await u.message.reply_text('❌ نام بات خالی است. دوباره ارسال کنید.', reply_markup=B.amenu())
        B.db.add_bot(st['bot_platform'], t, st['bot_token'])
        st['extra_step'] = None
        return await u.message.reply_text('✅ بات ثبت شد.', reply_markup=B.amenu())

    if t == '🤖 بات‌های متصل':
        rows = B.db.bots()
        txt = '\n'.join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) or 'هیچ باتی ثبت نشده است.'
        return await u.message.reply_text(txt, reply_markup=B.amenu())

    if t == '📣 اعلان خدمت':
        st['extra_step'] = 'done'
        return await u.message.reply_text('🎫 کد پیگیری خدمتی که انجام شده را بفرستید.\nمثال: NYM-AB12CD34', reply_markup=B.amenu())
    if step == 'done':
        r = B.db.conn.execute('SELECT * FROM requests WHERE tracking_code=?', (t,)).fetchone()
        if not r:
            return await u.message.reply_text('❌ کد پیگیری پیدا نشد.', reply_markup=B.amenu())
        B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?", (B.now(), r['id']))
        B.db.conn.commit()
        st['extra_step'] = None
        try:
            ur = B.db.conn.execute("SELECT external_id,platform FROM users WHERE id=?", (r['user_id'],)).fetchone()
            if ur:
                text = f"🔔 خدمت شما بروزرسانی شد.\n🎫 کد پیگیری: {r['tracking_code']}\n📌 وضعیت جدید: انجام شد ✅"
                if ur['platform'] == 'telegram':
                    await c.bot.send_message(chat_id=ur['external_id'], text=text)
                elif ur['platform'] == 'rubika':
                    try:
                        import rubika_v2 as rb
                        await __import__('asyncio').to_thread(rb.send, ur['external_id'], text, None)
                    except Exception:
                        pass
        except Exception:
            pass
        return await u.message.reply_text(f'✅ خدمت {t} به‌عنوان انجام‌شده ثبت شد.', reply_markup=B.amenu())

    return None


async def extra_cb(u, c):
    return None


def build():
    # B.router is replaced above, so all text/state handling is centralized in
    # one PTB handler. Do not add a second catch-all text handler: it causes
    # duplicate replies and corrupts multi-step flows.
    return B.build()


if __name__ == '__main__':
    app = build()
    webhook = os.getenv('TELEGRAM_WEBHOOK_URL', '').strip()
    if webhook:
        port = int(os.getenv('PORT', '8080'))
        path = webhook.rstrip('/').split('/')[-1]
        app.run_webhook(listen='0.0.0.0', port=port, url_path=path, webhook_url=webhook, allowed_updates=None)
    else:
        app.run_polling(allowed_updates=None)
