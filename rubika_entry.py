import os,time,logging,requests
from rubika_fixed import call,send,handle,S,db
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
log=logging.getLogger('netyar.rubika.entry')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
BASE=f'https://botapi.rubika.ir/v3/{TOKEN}'

def api(method,payload=None):
    r=requests.post(f'{BASE}/{method}',json=payload or {},timeout=45)
    r.raise_for_status(); data=r.json()
    return data.get('data',data) if isinstance(data,dict) else data

def normalize(u):
    if not isinstance(u,dict): return None
    msg=u.get('new_message') or u.get('updated_message')
    if not isinstance(msg,dict): return None
    chat=str(u.get('chat_id') or msg.get('chat_id') or '')
    uid=str(msg.get('sender_id') or '')
    if not chat or not uid: return None
    text=str(msg.get('text') or '').strip()
    if not text:
        aux=msg.get('aux_data') or {}
        if isinstance(aux,dict): text=str(aux.get('button_id') or '').strip()
    fid=''; f=msg.get('file')
    if isinstance(f,dict): fid=str(f.get('file_id') or '')
    return uid,chat,text,fid

def main():
    me=api('getMe'); log.info('Rubika getMe OK: %s',me.get('bot',me) if isinstance(me,dict) else me)
    offset=None; log.info('Rubika polling started (single owner)')
    while True:
        try:
            payload={'limit':50}
            if offset: payload['offset_id']=str(offset)
            result=api('getUpdates',payload)
            updates=result.get('updates',[]) if isinstance(result,dict) else []
            nxt=result.get('next_offset_id') if isinstance(result,dict) else None
            log.info('Rubika getUpdates OK: updates=%d next=%s',len(updates),nxt)
            for u in updates:
                p=normalize(u)
                if not p: continue
                uid,chat,text,fid=p
                try:
                    db.user('rubika',uid,'','')
                    if text.startswith('/start'):
                        S[uid]={'lang':'fa','step':'language'}
                        from rubika_fixed import lang_menu
                        send(chat,'🌐 زبان را انتخاب کنید:',lang_menu()); continue
                    if text.lower() in ('/admin2025','/admin'):
                        admins={x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}
                        if uid in admins:
                            S.setdefault(uid,{})['admin']=True; send(chat,'🛠 پنل مدیریت بات فعال شد.')
                        else: send(chat,'⛔ دسترسی ندارید.')
                        continue
                    value=text or fid
                    if value: handle(uid,chat,value)
                except Exception: log.exception('Rubika update handling failed uid=%s chat=%s',uid,chat)
            if nxt is not None: offset=str(nxt)
            time.sleep(.35 if updates else .8)
        except requests.RequestException as e:
            log.warning('Rubika API/network error: %s; retrying',e); time.sleep(3)
        except Exception:
            log.exception('Rubika polling loop error'); time.sleep(3)
if __name__=='__main__': main()
