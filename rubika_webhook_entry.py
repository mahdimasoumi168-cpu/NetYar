import json, os, threading, logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from rubika_entry import api, normalize, admin_flow, key, S, db, handle, ADMIN_COMMAND
from rubika_fixed import send, lang_menu
from admin_hub import menu as admin_menu

PORT=int(os.getenv('PORT','8080'))
PUBLIC=(os.getenv('PUBLIC_BASE_URL') or '').strip().rstrip('/')
if not PUBLIC:
    d=(os.getenv('RAILWAY_PUBLIC_DOMAIN') or '').strip()
    if d: PUBLIC='https://'+d
ENDPOINT=PUBLIC+'/rubika/update' if PUBLIC else ''
log=logging.getLogger('netyar.rubika.webhook'); logging.basicConfig(level=logging.INFO)

def process(update):
    p=normalize(update)
    if not p: return
    uid,chat,text,fid=p
    db.user('rubika',uid,'','')
    if text.startswith('/start') or update.get('type')=='StartedBot':
        S[uid]={'lang':'fa','step':'language'}; send(chat,'🌐 زبان را انتخاب کنید:',lang_menu()); return
    if text.lower() in (ADMIN_COMMAND,'/admin2025','/admin'):
        S.setdefault(uid,{})['admin']=True; send(chat,'🛠 پنل مدیریت پیشرفته فعال شد.',key(admin_menu())); return
    if S.get(uid,{}).get('admin') and admin_flow(uid,chat,text): return
    value=text or fid
    if value: handle(uid,chat,value)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): return
    def _ok(self,body=b'OK'):
        self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self._ok(b'NetYar Rubika webhook is running')
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length','0')); raw=self.rfile.read(n); update=json.loads(raw.decode('utf-8'))
            threading.Thread(target=process,args=(update,),daemon=True).start(); self._ok()
        except Exception as exc:
            log.exception('Rubika webhook update failed: %s',exc); self._ok(b'accepted')

def main():
    if not ENDPOINT: raise RuntimeError('PUBLIC_BASE_URL/RAILWAY_PUBLIC_DOMAIN is required for Rubika webhook')
    me=api('getMe'); log.info('Rubika getMe OK: %s',me)
    result=api('updateBotEndpoints',{'url':ENDPOINT,'type':'ReceiveUpdate'}); log.info('Rubika ReceiveUpdate endpoint registered: %s | %s',ENDPOINT,result)
    server=ThreadingHTTPServer(('0.0.0.0',PORT),Handler); log.info('Rubika webhook listening on port %s',PORT); server.serve_forever()

if __name__=='__main__': main()
