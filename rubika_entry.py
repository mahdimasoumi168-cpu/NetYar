import os,time,logging,requests
from rubika_fixed import call,send,handle,S,db
from admin_hub import menu as admin_menu,render as render_bots,PLATFORMS,add_bot
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
log=logging.getLogger('netyar.rubika.entry')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
if not TOKEN: raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
BASE=f'https://botapi.rubika.ir/v3/{TOKEN}'
ADMIN_COMMAND=os.getenv('ADMIN_COMMAND','/Admin2025').strip().lower()
def api(method,payload=None):
 r=requests.post(f'{BASE}/{method}',json=payload or {},timeout=45);r.raise_for_status();data=r.json();return data.get('data',data) if isinstance(data,dict) else data
def key(rows):return [[(str(i),label) for i,label in row] for row in rows]
def normalize(u):
 if not isinstance(u,dict):return None
 msg=u.get('new_message') or u.get('updated_message')
 if not isinstance(msg,dict):return None
 chat=str(u.get('chat_id') or msg.get('chat_id') or '');uid=str(msg.get('sender_id') or '')
 if not chat or not uid:return None
 text=str(msg.get('text') or '').strip()
 if not text:
  aux=msg.get('aux_data') or {}
  if isinstance(aux,dict):text=str(aux.get('button_id') or '').strip()
 fid='';f=msg.get('file')
 if isinstance(f,dict):fid=str(f.get('file_id') or '')
 return uid,chat,text,fid
def is_admin(uid):return uid in {x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}
def admin_flow(uid,chat,text):
 st=S.setdefault(uid,{});step=st.get('admin_step')
 if text=='a_bots':send(chat,render_bots(),key(admin_menu()));return True
 if text=='a_addbot':st['admin_step']='platform';send(chat,'🤖 پیام‌رسان را انتخاب کنید:',key([[('rubika','🟣 روبیکا'),('telegram','🔵 تلگرام')],[('eitaa','🟠 ایتا'),('bale','🟢 بله')],[('cancel','❌ انصراف')]]));return True
 if text=='a_partners':
  rows=db.conn.execute('SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC').fetchall();send(chat,'👥 همکاران\n'+'\n'.join(f"#{r['id']} | {r['name']} | {r['phone']} | {int(r['balance']):,}" for r in rows) or 'همکاری ثبت نشده.',key(admin_menu()));return True
 if text=='a_reports':
  p=db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0];q=db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0];t=db.conn.execute("SELECT COUNT(*) FROM topups WHERE status='pending'").fetchone()[0];send(chat,f'📊 گزارش کامل\n👥 همکاران: {p}\n📋 درخواست‌ها: {q}\n💰 شارژهای منتظر تأیید: {t}',key(admin_menu()));return True
 if text=='a_prices':st['admin_step']='price';send(chat,'💰 قیمت را این‌طور بفرستید:\ngovernment 500000',key(admin_menu()));return True
 if text=='a_notify':send(chat,'🔔 سیستم اعلان آماده است؛ وضعیت خدمات از همین پنل قابل مدیریت است.',key(admin_menu()));return True
 if text=='a_exit':st['admin']=False;st.pop('admin_step',None);send(chat,'✅ از مدیریت خارج شدید.');return True
 if step=='platform' and text in PLATFORMS:st['bot_platform']=text;st['admin_step']='bot_name';send(chat,'📝 نام این بات را وارد کنید:');return True
 if step=='bot_name':st['bot_name']=text;st['admin_step']='bot_token';send(chat,'🔐 API Token را ارسال کنید. توکن خام در دیتابیس ذخیره نمی‌شود؛ فقط برای اعتبارسنجی لحظه‌ای استفاده می‌شود.');return True
 if step=='bot_token':
  try:
   ok,ref=add_bot(st['bot_platform'],st['bot_name'],text);st.pop('admin_step',None);send(chat,(f'✅ API معتبر بود و بات ثبت شد.\n🔑 Secret reference: {ref}\n⚠️ برای اجرای دائمی، توکن را با همین نام در Railway Secrets تنظیم کن.' if ok else f'⚠️ رکورد ثبت شد ولی API اعتبارسنجی نشد.\n🔑 Secret reference: {ref}'),key(admin_menu()));return True
  except Exception as e:send(chat,f'❌ خطا در اعتبارسنجی API: {e}',key(admin_menu()));return True
 if step=='price':
  a=text.split()
  if len(a)==2 and a[1].isdigit():db.set_setting('price_'+a[0],int(a[1]));st.pop('admin_step',None);send(chat,'✅ قیمت ذخیره شد.',key(admin_menu()));return True
  send(chat,'❌ قالب نادرست است. مثال: government 500000');return True
 return False
def main():
 me=api('getMe');log.info('Rubika getMe OK: %s',me.get('bot',me) if isinstance(me,dict) else me);offset=None;log.info('Rubika polling started (single owner)')
 while True:
  try:
   payload={'limit':50}
   if offset:payload['offset_id']=str(offset)
   result=api('getUpdates',payload);updates=result.get('updates',[]) if isinstance(result,dict) else [];nxt=result.get('next_offset_id') if isinstance(result,dict) else None
   log.info('Rubika getUpdates OK: updates=%d next=%s',len(updates),nxt)
   for u in updates:
    p=normalize(u)
    if not p:continue
    uid,chat,text,fid=p
    try:
     db.user('rubika',uid,'','')
     if text.startswith('/start'):
      S[uid]={'lang':'fa','step':'language'}
      from rubika_fixed import lang_menu
      send(chat,'🌐 زبان را انتخاب کنید:',lang_menu());continue
     if text.lower() in (ADMIN_COMMAND,'/admin2025','/admin'):
      S.setdefault(uid,{})['admin']=True;send(chat,'🛠 پنل مدیریت پیشرفته فعال شد.',key(admin_menu()));continue
     if S.get(uid,{}).get('admin') and admin_flow(uid,chat,text):continue
     value=text or fid
     if value:handle(uid,chat,value)
    except Exception:log.exception('Rubika update handling failed uid=%s chat=%s',uid,chat)
   if nxt is not None:offset=str(nxt)
   time.sleep(.35 if updates else .8)
  except requests.RequestException as e:log.warning('Rubika API/network error: %s; retrying',e);time.sleep(3)
  except Exception:log.exception('Rubika polling loop error');time.sleep(3)
if __name__=='__main__':main()
