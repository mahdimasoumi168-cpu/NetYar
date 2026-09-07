import json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import rubika_fixed as bot

PORT = int(os.getenv('PORT', '8080'))
PUBLIC = (os.getenv('PUBLIC_BASE_URL') or '').strip().rstrip('/')
if not PUBLIC:
    domain = (os.getenv('RAILWAY_PUBLIC_DOMAIN') or '').strip()
    if domain:
        PUBLIC = 'https://' + domain
ENDPOINT = PUBLIC + '/rubika/update' if PUBLIC else ''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return
    def _ok(self, body=b'OK'):
        self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        self._ok(b'NetYar Rubika webhook is running')
    def do_POST(self):
        try:
            n = int(self.headers.get('Content-Length','0'))
            raw = self.rfile.read(n)
            update = json.loads(raw.decode('utf-8'))
            threading.Thread(target=bot.process, args=(update,), daemon=True).start()
            self._ok()
        except Exception as exc:
            bot.log.exception('Rubika webhook update failed: %s', exc)
            self._ok(b'accepted')

def register_endpoint():
    if not ENDPOINT:
        raise RuntimeError('No public URL available for Rubika webhook')
    result = bot.call('updateBotEndpoints', {'url': ENDPOINT, 'type': 'ReceiveUpdate'})
    bot.log.info('Rubika webhook registered: %s', ENDPOINT)
    return result

def main():
    bot.log.info('Rubika getMe OK: %s', bot.call('getMe'))
    register_endpoint()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    bot.log.info('NetYar Rubika webhook listening on 0.0.0.0:%s', PORT)
    server.serve_forever()

if __name__ == '__main__':
    main()
