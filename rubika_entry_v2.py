import os,time,logging,requests
from rubika_fixed import call,send,handle,S,db,lang_menu
from admin_hub import PLATFORMS,add_bot,render as render_bots
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
log=logging.getLogger('netyar.rubika.v2')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
BASE=f'https://botapi.rubika.ir/v3/{TOKEN}'
ADMIN_COMMAND=os.getenv('ADMIN_COMMAND','/Admin2025').strip().lower()

def api(method,payload=None):
    r=requests.post(f'{BASE}/{method}',json=payload or {},timeout=45); r.raise_for_status()
    data=r.json(); return data.get('data',data) if isinstance(data,dict) else data

def key(rows): return [[(str(i),label) for i,label in row] for row in rows]

def admin_menu():
    return key([
      [('a_partners','👥 مدیریت همکاران'),('a_bots','🤖 مدیریت بات‌ها')],
      [('a_addbot','➕ افزودن بات'),('a_notify','🔔 اعلان‌ها')],
      [('a_requests','📋 مدیریت درخواست‌ها'),('a_reports','📊 گزارش کامل')],
      [('a_prices','💰 مدیریت قیمت‌ها'),('a_services','⚙️ خدمات')],
      [('a_exit','🚪 خروج')]
    ])

def normalize(u):
    if not isinstance(u,dict): return None
    msg=u.get('new_message') or u.get('updated_message')
    # StartedBot/StoppedBot updates contain chat_id but may not contain new_message.
    # Keep the event so /start-style onboarding is deterministic.
    chat=str(u.get('chat_id') or (msg or {}).get('chat_id') or '')
    if not chat:return None
    if not isinstance(msg,dict):
        return chat,chat,'__STARTED__' if u.get('type')=='StartedBot' else '__EVENT__',''
    uid=str(msg.get('sender_id') or msg.get('author_id') or chat)
    text=str(msg.get('text') or '').strip()
    aux=msg.get('aux_data') or {}
    if not text and isinstance(aux,dict): text=str(aux.get('button_id') or aux.get('button_id_string') or aux.get('text') or '').strip()
    fid=''; f=msg.get('file')
    if isinstance(f,dict): fid=str(f.get('file_id') or '')
    return uid,chat,text,fid

def is_admin(uid):
    return uid in {x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}

def language_value(x):
    x=str(x or '').strip()
    return {'lang:fa':'1','lang:en':'2','lang:ar':'3','1':'1','2':'2','3':'3','فارسی':'1','🇮🇷 فارسی':'1','English':'2','🇬🇧 English':'2','العربية':'3','🇸🇦 العربية':'3'}.get(x)

def notify_partner(partner_id,text):
    try:
        row=db.conn.execute("SELECT value FROM settings WHERE key=?",(f'partner_chat_{partner_id}',)).fetchone()
        if row and row['value']:
            send(row['value'],text); return True
    except Exception: log.exception('partner notification failed')
    return False

def admin_flow(uid,chat,text):
    st=S.setdefault(uid,{})
    step=st.get('admin_step')
    if text=='a_bots': send(chat,render_bots(),admin_menu()); return True
    if text=='a_addbot':
        st['admin_step']='platform'; send(chat,'🤖 پیام‌رسان را انتخاب کنید:',key([[('rubika','🟣 روبیکا'),('telegram','🔵 تلگرام')],[('eitaa','🟠 ایتا'),('bale','🟢 بله')],[('cancel','❌ انصراف')]])); return True
    if text=='a_partners':
        rows=db.conn.execute('SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC').fetchall()
        send(chat,'👥 همکاران\n'+'\n'.join(f"#{r['id']} | {r['name']} | {r['phone']} | {int(r['balance']):,} تومان | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or 'همکاری ثبت نشده.',admin_menu()); return True
    if text=='a_requests':
        rows=db.conn.execute('SELECT id,tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 20').fetchall()
        if not rows: send(chat,'📋 درخواستی ثبت نشده است.',admin_menu()); return True
        lines=['📋 آخرین درخواست‌ها:','']+[f"#{r['id']} | {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,} تومان | {r['payment_status']}" for r in rows]
        rows_btn=[[(f'req:{r["id"]}:processing',f'▶️ شروع #{r["id"]}'),(f'req:{r["id"]}:done',f'✅ اتمام #{r["id"]}')] for r in rows[:10]]; rows_btn.append([('req:back','↩️ مدیریت')])
        send(chat,'\n'.join(lines),key(rows_btn)); return True
    if text.startswith('req:'):
        parts=text.split(':')
        if len(parts)==3 and parts[1].isdigit():
            rid=int(parts[1]); status=parts[2]
            if status=='back': send(chat,'🛠 مدیریت:',admin_menu()); return True
            label={'processing':'در حال انجام','done':'انجام شد'}.get(status,status)
            row=db.conn.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if not row: send(chat,'❌ درخواست پیدا نشد.',admin_menu()); return True
            db.conn.execute("UPDATE requests SET status=?,updated_at=datetime('now') WHERE id=?",(label,rid)); db.conn.commit()
            pr=db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(rid,)).fetchone()
            if pr: notify_partner(pr['answer'],f"🔔 وضعیت درخواست شما تغییر کرد.\n🎫 کد پیگیری: {row['tracking_code']}\n📌 وضعیت جدید: {label}")
            send(chat,f'✅ وضعیت درخواست #{rid} به «{label}» تغییر کرد.',admin_menu()); return True
    if text=='a_reports':
        p=db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0]; q=db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0]; t=db.conn.execute("SELECT COUNT(*) FROM topups WHERE status='pending'").fetchone()[0]
        send(chat,f'📊 گزارش کامل\n👥 همکاران: {p}\n📋 درخواست‌ها: {q}\n💰 شارژهای منتظر تأیید: {t}',admin_menu()); return True
    if text=='a_prices': st['admin_step']='price'; send(chat,'💰 قیمت را این‌طور بفرستید:\ngovernment 500000',admin_menu()); return True
    if text=='a_services':
        rows=db.conn.execute('SELECT key,name,price,active FROM services ORDER BY id').fetchall(); send(chat,'\n'.join(f"{r['key']} | {r['name']} | {int(r['price']):,} تومان | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or 'خدمتی نیست.',admin_menu()); return True
    if text=='a_notify': send(chat,'🔔 اعلان خودکار وضعیت خدمات فعال است. با هر تغییر وضعیت، در صورت ثبت شناسه پنل همکار، پیام خودکار ارسال می‌شود.',admin_menu()); return True
    if text=='a_exit': st['admin']=False; st.pop('admin_step',None); send(chat,'✅ از مدیریت خارج شدید.'); return True
    if step=='platform' and text in PLATFORMS:
        st['bot_platform']=text; st['admin_step']='bot_name'; send(chat,'📝 نام این بات را وارد کنید:',key([[('cancel','❌ انصراف')]])); return True
    if step=='bot_name':
        if text in {'cancel','0'}: st.pop('admin_step',None); send(chat,'لغو شد.',admin_menu()); return True
        st['bot_name']=text; st['admin_step']='bot_token'; send(chat,'🔐 API Token را ارسال کنید.'); return True
    if step=='bot_token':
        try:
            ok,ref=add_bot(st['bot_platform'],st['bot_name'],text); st.pop('admin_step',None)
            send(chat,(f'✅ API معتبر است و بات ثبت شد.\n🔑 Secret reference: {ref}' if ok else f'⚠️ رکورد ثبت شد ولی API اعتبارسنجی نشد.\n🔑 Secret reference: {ref}'),admin_menu()); return True
        except Exception as e: send(chat,f'❌ خطا: {e}',admin_menu()); return True
    if step=='price':
        a=text.split()
        if len(a)==2 and a[1].isdigit(): db.set_setting('price_'+a[0],int(a[1])); st.pop('admin_step',None); send(chat,'✅ قیمت ذخیره شد.',admin_menu()); return True
        send(chat,'❌ قالب نادرست است. مثال: government 500000'); return True
    return False

def main():
    me=api('getMe'); log.info('Rubika getMe OK: %s',me.get('bot',me) if isinstance(me,dict) else me)
    offset=None; log.info('Rubika polling started: stable v3')
    while True:
        try:
            payload={'limit':50}
            if offset: payload['offset_id']=str(offset)
            result=api('getUpdates',payload)
            updates=result.get('updates',[]) if isinstance(result,dict) else []
            nxt=result.get('next_offset_id') if isinstance(result,dict) else None
            log.info('Rubika getUpdates OK: %d update(s)',len(updates))
            for u in updates:
                p=normalize(u)
                if not p: continue
                uid,chat,text,fid=p
                try:
                    db.user('rubika',uid,'','')
                    if text=='__STARTED__' or text.lower().startswith('/start'):
                        S[uid]={'lang':'fa','step':'language'}
                        send(chat,'🌐 زبان را انتخاب کنید:',key([[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])); continue
                    if text.lower() in {ADMIN_COMMAND,'/admin2025','/admin'} and is_admin(uid):
                        S.setdefault(uid,{})['admin']=True; S[uid]['admin_step']=None; send(chat,'🛠 پنل مدیریت پیشرفته و کامل:',admin_menu()); continue
                    if S.get(uid,{}).get('admin') and admin_flow(uid,chat,text): continue
                    if S.get(uid,{}).get('step')=='language':
                        lv=language_value(text)
                        if lv: text=lv
                    before=S.get(uid,{}).copy()
                    handle(uid,chat,text or fid, {'file':{'file_id':fid}} if fid else {})
                    after=S.get(uid,{})
                    if before.get('step')=='pw' and after.get('partner_id'):
                        db.set_setting(f"partner_chat_{after['partner_id']}",chat)
                except Exception: log.exception('Rubika update handling failed uid=%s chat=%s',uid,chat)
            if nxt is not None: offset=str(nxt)
            time.sleep(.25 if updates else .8)
        except requests.RequestException as e: log.warning('Rubika API/network error: %s; retrying',e); time.sleep(3)
        except Exception: log.exception('Rubika polling loop error'); time.sleep(3)

if __name__=='__main__': main()
