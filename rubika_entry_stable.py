import os,time,logging,requests
import rubika_v2 as bot
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
log=logging.getLogger('netyar.rubika.stable')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
ADM={x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}
ADMIN_COMMAND=os.getenv('ADMIN_COMMAND','/Admin2025').strip().lower()

_orig_admin_rows=bot.admin_rows
_orig_admin=bot.admin
def admin_rows_extended():
    r=_orig_admin_rows()
    if not any(any(str(b[0])=='9' for b in row) for row in r): r.insert(-1,[('9','➕ افزودن همکار')])
    return r
bot.admin_rows=admin_rows_extended

def admin_extended(uid,chat,x):
    st=bot.STATE[str(uid)]
    if st.get('partner_add')=='phone':
        st['new_partner_phone']=x; st['partner_add']='name'; bot.send(chat,'👤 نام همکار را وارد کنید:'); return
    if st.get('partner_add')=='name':
        st['new_partner_name']=x; st['partner_add']='password'; bot.send(chat,'🔐 رمز عبور همکار را وارد کنید:'); return
    if st.get('partner_add')=='password':
        try:
            bot.db.add_partner(st['new_partner_phone'],x,st['new_partner_name'])
            st.pop('partner_add',None); bot.send(chat,'✅ همکار با موفقیت اضافه شد.\n📱 شماره و رمز برای ورود پنل همکاران فعال شد.',admin_rows_extended()); return
        except Exception:
            bot.send(chat,'❌ این شماره قبلاً ثبت شده یا اطلاعات نامعتبر است.',admin_rows_extended()); return
    if st.get('step')=='admin' and (x=='9' or 'افزودن همکار' in x):
        st['partner_add']='phone'; bot.send(chat,'📱 شماره همراه همکار جدید را وارد کنید:'); return
    return _orig_admin(uid,chat,x)
bot.admin=admin_extended

def main():
    if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
    me=bot.call('getMe'); log.info('Rubika getMe OK: %s',me)
    offset=None; log.info('Rubika stable polling started')
    while True:
        try:
            p={'limit':50}
            if offset:p['offset_id']=str(offset)
            d=bot.call('getUpdates',p)
            updates=d.get('updates',[]) if isinstance(d,dict) else []
            nxt=d.get('next_offset_id') if isinstance(d,dict) else None
            log.info('Rubika getUpdates OK: %d update(s)',len(updates))
            for u in updates:
                try:
                    uid=bot.user_of(u); chat=bot.chat_of(u); text=bot.text_of(u).strip().lower()
                    if text in {ADMIN_COMMAND,'/admin2025','/admin'} and uid not in ADM:
                        bot.send(chat,'⛔ دسترسی مدیریت ندارید.'); continue
                    bot.process(u)
                except Exception: log.exception('Rubika update failed')
            if nxt is not None: offset=str(nxt)
            time.sleep(.25 if updates else .8)
        except requests.RequestException as e: log.warning('Rubika network/API error: %s',e); time.sleep(3)
        except Exception: log.exception('Rubika polling error'); time.sleep(3)
if __name__=='__main__': main()
