import os, time, logging, requests
import rubika_hotfix as base
rb = base.rb
log = logging.getLogger("netyar.rubika.v3")

# ---- Stable language handling ----
LANG = {
    "lang:fa":"fa", "lang:en":"en", "lang:ar":"ar",
    "1":"fa", "2":"en", "3":"ar",
    "فارسی":"fa", "🇮🇷 فارسی":"fa", "farsi":"fa", "fa":"fa",
    "English":"en", "🇬🇧 English":"en", "english":"en", "en":"en",
    "العربية":"ar", "🇸🇦 العربية":"ar", "arabic":"ar", "ar":"ar",
}

def normalize_language(value):
    raw=str(value or "").strip()
    if raw in LANG: return LANG[raw]
    for prefix in ("🇮🇷 ","🇬🇧 ","🇸🇦 "):
        if raw.startswith(prefix) and raw[len(prefix):] in LANG:
            return LANG[raw[len(prefix):]]
    return None
base._lang_choice = normalize_language

def stable_lang_menu():
    # Use both a visible text and a deterministic button id. Rubika may return either text or aux_data.button_id.
    return rb.buttons([[('lang:fa','🇮🇷 فارسی'),('lang:en','🇬🇧 English'),('lang:ar','🇸🇦 العربية')]])
rb.lang_menu = stable_lang_menu

_old_handle_text = rb.handle_text
_old_admin_menu = rb.admin_menu
_old_admin_action = rb.admin_action

# ---- Advanced management panel ----
def advanced_admin_menu():
    return rb.buttons([
        [('1','👥 مدیریت همکاران'),('2','💰 شارژها')],
        [('3','💳 پرداخت‌ها'),('4','📋 درخواست‌ها')],
        [('5','⚙️ قیمت خدمات'),('6','📊 گزارش')],
        [('7','🤖 افزودن/مدیریت بات'),('8','🔔 اعلان‌های خدمات')],
        [('9','🧾 وضعیت سرویس‌ها'),('0','🚪 خروج')],
    ])
rb.admin_menu = advanced_admin_menu

def _bot_platform_menu():
    return rb.buttons([[('bot:telegram','🤖 تلگرام'),('bot:rubika','🟣 روبیکا')],[('bot:eitaa','🟢 ایتا'),('bot:bale','🔵 بله')],[('0',rb.CANCEL)]])

def _bot_list(chat):
    rows=rb.db.bots()
    if not rows:
        rb.send(chat,'🤖 هنوز پیام‌رسانی ثبت نشده است.',advanced_admin_menu()); return
    lines=['🤖 پیام‌رسان‌های ثبت‌شده:','']
    for r in rows:
        lines.append(f"#{r['id']} | {r['platform']} | {r['bot_name'] or '-'} | {'🟢 فعال' if r['active'] else '⚪ غیرفعال'} | {r['status']}")
    rb.send(chat,'\n'.join(lines),advanced_admin_menu())

def _add_bot_start(uid,chat):
    rb.STATES[uid]['step']='admin_bot_platform'
    rb.send(chat,'🤖 پیام‌رسان موردنظر را انتخاب کنید:',_bot_platform_menu())

def _bot_token_start(uid,chat,platform):
    rb.STATES[uid]['bot_platform']=platform
    rb.STATES[uid]['step']='admin_bot_name'
    rb.send(chat,'📝 نام این بات را وارد کنید:',rb.buttons([[('0',rb.CANCEL)]]))

def _save_bot(uid,chat):
    st=rb.STATES[uid]
    platform=st.get('bot_platform','').strip(); name=st.get('bot_name','').strip(); token=st.get('bot_token','').strip()
    if not platform or not token:
        rb.send(chat,'❌ اطلاعات بات کامل نیست.',advanced_admin_menu()); st['step']='admin_menu'; return
    status='configured'
    # Validate Rubika immediately. Other adapters are registered but activated only after their official API adapter is available.
    if platform=='rubika':
        try:
            url=f"https://botapi.rubika.ir/v3/{token}/getMe"
            res=requests.post(url,timeout=15)
            if res.ok:
                status='connected'
            else:
                status='invalid_token'
        except Exception:
            status='connection_error'
    elif platform in {'eitaa','bale','telegram'}:
        status='configured'
    rb.db.add_bot(platform,name,token)
    rb.db.conn.execute('UPDATE bot_integrations SET status=?,active=?,updated_at=? WHERE platform=?',(status,1 if status=='connected' else 0,rb.now(),platform)); rb.db.conn.commit()
    rb.send(chat,f"✅ بات ثبت شد.\n\n📡 پیام‌رسان: {platform}\n🤖 نام: {name}\n📌 وضعیت: {status}",advanced_admin_menu())
    st['step']='admin_menu'; st.pop('bot_platform',None); st.pop('bot_name',None); st.pop('bot_token',None)

def advanced_admin_action(uid,chat,text):
    if text in {'7','🤖 افزودن/مدیریت بات'}:
        _add_bot_start(uid,chat); return True
    if text in {'8','🔔 اعلان‌های خدمات'}:
        rb.send(chat,'🔔 اعلان خودکار فعال است:\nثبت درخواست → پرداخت → تأیید → شروع خدمت → تغییر وضعیت → اتمام خدمت.\n\nبرای اتصال اعلان به پیام‌رسان جدید، ابتدا آن بات را از گزینه «افزودن/مدیریت بات» ثبت کنید.',advanced_admin_menu()); return True
    if text in {'9','🧾 وضعیت سرویس‌ها'}:
        rows=rb.db.conn.execute('SELECT key,name,price,active FROM services ORDER BY id').fetchall()
        rb.send(chat,'\n'.join(f"{r['key']} | {r['name']} | {int(r['price']):,} تومان | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or 'سرویسی ثبت نشده.',advanced_admin_menu()); return True
    if text in {'0','🚪 خروج'}:
        rb.STATES[uid]['admin']=False; rb.STATES[uid]['step']='menu'; rb.send(chat,'✅ از پنل مدیریت خارج شدید.',rb.main_menu(rb.STATES[uid].get('lang','fa'))); return True
    if text in {'🤖 پیام‌رسان‌ها','لیست بات‌ها'}:
        _bot_list(chat); return True
    return _old_admin_action(uid,chat,text)
rb.admin_action = advanced_admin_action

# ---- Admin flow extensions + bulletproof language flow ----
def handle_text(uid,chat,text):
    st=rb.new_state(uid)
    step=st.get('step')
    if step=='language':
        chosen=normalize_language(text)
        if not chosen:
            rb.send(chat,rb.TEXT['fa']['lang'],stable_lang_menu()); return
        st['lang']=chosen; st['step']='citizenship'
        rb.send(chat,rb.TEXT[chosen]['cit'],rb.citizenship_menu(chosen)); return
    if st.get('admin') and step=='admin_menu':
        if advanced_admin_action(uid,chat,text): return
    if st.get('admin') and step=='admin_bot_platform':
        if rb.is_cancel(text): rb.cancel(uid,chat); return
        raw=str(text).strip()
        p={'bot:telegram':'telegram','bot:rubika':'rubika','bot:eitaa':'eitaa','bot:bale':'bale'}.get(raw)
        if not p:
            p={'1':'telegram','2':'rubika','3':'eitaa','4':'bale'}.get(raw)
        if not p:
            rb.send(chat,'لطفاً پیام‌رسان را انتخاب کنید.',_bot_platform_menu()); return
        _bot_token_start(uid,chat,p); return
    if st.get('admin') and step=='admin_bot_name':
        if rb.is_cancel(text): rb.cancel(uid,chat); return
        if not str(text).strip():
            rb.send(chat,'نام بات را وارد کنید.',rb.buttons([[('0',rb.CANCEL)]])); return
        st['bot_name']=str(text).strip(); st['step']='admin_bot_token'
        rb.send(chat,'🔐 API Token بات را ارسال کنید.\n\nتوکن در پیام‌های عمومی نمایش داده نمی‌شود.',rb.buttons([[('0',rb.CANCEL)]])); return
    if st.get('admin') and step=='admin_bot_token':
        if rb.is_cancel(text): rb.cancel(uid,chat); return
        st['bot_token']=str(text).strip(); _save_bot(uid,chat); return
    return _old_handle_text(uid,chat,text)
rb.handle_text = handle_text

# Preserve media workflow from the existing implementation.
rb.handle_media = base.handle_media

# Ensure the manager command opens the advanced panel even if ADMIN_IDS is configured.
_old_run = rb.run
def run():
    rb.admin_menu=advanced_admin_menu
    rb.handle_text=handle_text
    log.info('NetYar Rubika v3 starting with stable language/admin adapter')
    return _old_run()
rb.run=run

if __name__=='__main__':
    run()
