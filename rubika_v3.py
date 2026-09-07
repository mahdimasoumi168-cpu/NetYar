import rubika_v2

def chat_of(u):
    m=u.get('new_message') or u.get('updated_message') or u.get('message') or {}
    return str(u.get('chat_id') or m.get('chat_id') or '')

def user_of(u):
    m=u.get('new_message') or u.get('updated_message') or u.get('message') or {}
    return str(m.get('sender_id') or m.get('user_id') or u.get('user_id') or u.get('chat_id') or m.get('chat_id') or '')

def text_of(u):
    m=u.get('new_message') or u.get('updated_message') or u.get('message') or {}
    text=str(m.get('text') or '').strip()
    if text:return text
    aux=m.get('aux_data') or {}
    if isinstance(aux,dict):return str(aux.get('button_id') or aux.get('button_text') or '').strip()
    return ''

def admin_rows():
    return [[('1','👥 همکاران'),('2','💰 شارژها')],[('3','📋 درخواست‌ها'),('4','💳 پرداخت‌ها')],[('5','⚙️ قیمت‌ها'),('6','🤖 افزودن بات')],[('7','🤖 بات‌های متصل'),('8','📊 گزارش')],[('9','➕ افزودن همکار'),('10','🔔 تکمیل خدمت')],[('0','⬅️ منوی اصلی')]]

_old_admin=rubika_v2.admin
def admin(uid,chat,x):
    st=rubika_v2.STATE[str(uid)];step=st.get('step')
    if step=='partner_add_phone':st['new_phone']=x;st['step']='partner_add_name';rubika_v2.send(chat,'👤 نام همکار را وارد کنید:');return
    if step=='partner_add_name':st['new_name']=x;st['step']='partner_add_pass';rubika_v2.send(chat,'🔐 رمز عبور همکار را وارد کنید:');return
    if step=='partner_add_pass':
        try:rubika_v2.db.add_partner(st['new_phone'],x,st['new_name']);rubika_v2.send(chat,'✅ همکار با موفقیت ایجاد شد.',admin_rows())
        except Exception:rubika_v2.send(chat,'❌ ثبت همکار انجام نشد؛ شماره ممکن است تکراری باشد.',admin_rows())
        st['step']='admin';return
    if step=='service_done_code':
        r=rubika_v2.db.conn.execute('SELECT id,tracking_code,user_id,platform FROM requests WHERE tracking_code=?',(x,)).fetchone()
        if not r:rubika_v2.send(chat,'❌ کد پیگیری پیدا نشد.',admin_rows());return
        st['done_rid']=r['id'];st['step']='service_done_text';rubika_v2.send(chat,'📝 متن پیام تکمیل خدمت را وارد کنید؛ یا «خودکار».');return
    if step=='service_done_text':
        r=rubika_v2.db.conn.execute('SELECT tracking_code,user_id,platform FROM requests WHERE id=?',(st['done_rid'],)).fetchone()
        rubika_v2.db.conn.execute("UPDATE requests SET status='done',updated_at=datetime('now') WHERE id=?",(st['done_rid'],));rubika_v2.db.conn.commit()
        text=f"✅ خدمت شما با موفقیت انجام شد.\n🎫 کد پیگیری: {r['tracking_code']}" if x=='خودکار' else x
        u=rubika_v2.db.conn.execute('SELECT external_id FROM users WHERE id=?',(r['user_id'],)).fetchone()
        if u and r['platform']=='rubika':
            try:rubika_v2.send(u['external_id'],text)
            except Exception:rubika_v2.log.exception('completion notification failed')
        st['step']='admin';rubika_v2.send(chat,'✅ خدمت تکمیل شد و پیام خودکار برای مشتری ارسال شد.',admin_rows());return
    if step=='admin':
        if x in ('9','➕ افزودن همکار'):st['step']='partner_add_phone';rubika_v2.send(chat,'📱 شماره همراه همکار را وارد کنید:');return
        if x in ('10','🔔 تکمیل خدمت'):st['step']='service_done_code';rubika_v2.send(chat,'🎫 کد پیگیری خدمت را وارد کنید:');return
    return _old_admin(uid,chat,x)

rubika_v2.chat_of=chat_of;rubika_v2.user_of=user_of;rubika_v2.text_of=text_of;rubika_v2.admin_rows=admin_rows;rubika_v2.admin=admin
rubika_v2.log.info('Rubika v3 routing/admin hotfix loaded')
if __name__=='__main__':rubika_v2.main()
