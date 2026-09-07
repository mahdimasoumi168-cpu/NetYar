import os
import time
import logging
import requests
import rubika_fixed as app

logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO)
log = logging.getLogger('netyar.rubika.runner')
TOKEN = os.getenv('RUBIKA_BOT_TOKEN','').strip()
if not TOKEN:
    raise RuntimeError('RUBIKA_BOT_TOKEN is missing')
BASE = f'https://botapi.rubika.ir/v3/{TOKEN}'
HTTP = requests.Session()
HTTP.headers.update({'Content-Type':'application/json'})

# Rubika returns button clicks in aux_data.button_id. Older implementations often
# looked only at message.text, which makes the language/citizenship keypad appear
# to work while every click is effectively ignored.
LABEL_TO_ID = {
    '🇮🇷 فارسی':'1','فارسی':'1','🇬🇧 English':'2','English':'2','🇸🇦 العربية':'3','العربية':'3',
    '🪪 اتباع هستم':'1','🪪 Foreign national':'1','🪪 أجنبي':'1','🇮🇷 ایرانی هستم':'2','🇮🇷 Iranian':'2','🇮🇷 إيراني':'2',
    '🪪 فیدای غیر حضوری':'1','🪪 FIDA non-in-person':'1','🪪 خدمة فيدا':'1',
    '🖨 خدمات چاپ':'2','🖨 Printing':'2','🖨 الطباعة':'2',
    '🏛 حل مشکل ورود اتباع دولت من':'3','🏛 Government access issue':'3','🏛 مشكلة خدمات الحكومة':'3',
    '🎫 پیگیری':'4','🎫 Tracking':'4','🎫 متابعة':'4',
    '📱 خدمات سیم کارت':'5','📱 SIM services':'5','📱 خدمات الشريحة':'5',
    '📝 آزمون غربالگری و پیگیری':'6','📝 Screening & follow-up':'6','📝 الفحص والمتابعة':'6',
    '💰 کیف پول من':'7','💰 My wallet':'7','💰 محفظتي':'7',
    '👥 پنل همکاران':'8','👥 Partner panel':'8','👥 لوحة الشركاء':'8',
    '📞 تماس با ما':'9','📞 Contact us':'9','📞 اتصل بنا':'9',
    '❌ انصراف':'0','❌ Cancel':'0','❌ إلغاء':'0','انصراف':'0','لغو':'0','Cancel':'0','cancel':'0','إلغاء':'0',
    '➕ شارژ حساب':'1','🔎 پیگیری کد':'2','📋 سوابق':'3','💰 موجودی':'4',
    '⚫ سیاه و سفید':'1','⚫ Black & white':'1','⚫ أبيض وأسود':'1','🌈 رنگی':'2','🌈 Color':'2','🌈 ملون':'2',
}

def api(method, payload=None):
    r = HTTP.post(f'{BASE}/{method}', json=payload or {}, timeout=35)
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict) and 'data' in body:
        return body['data']
    return body

def extract_updates(body):
    if isinstance(body, dict):
        u = body.get('updates')
        if isinstance(u, list):
            return u, body.get('next_offset_id')
        # Some API/proxy responses put data one level deeper.
        d = body.get('data')
        if isinstance(d, dict):
            return d.get('updates') or [], d.get('next_offset_id')
    return [], None

def extract_message(update):
    if not isinstance(update, dict): return None
    msg = update.get('new_message') or update.get('updated_message')
    if not isinstance(msg, dict): return None
    chat = update.get('chat_id') or msg.get('chat_id')
    sender = msg.get('sender_id') or msg.get('user_id') or chat
    return str(sender), str(chat), msg

def extract_input(msg):
    # Text has priority; button_id is the authoritative value for chat keypad clicks.
    text = str(msg.get('text') or '').strip()
    aux = msg.get('aux_data') or {}
    if isinstance(aux, dict):
        bid = str(aux.get('button_id') or '').strip()
        if bid: return bid
    if text in LABEL_TO_ID: return LABEL_TO_ID[text]
    return text

def reset_start(uid, chat):
    app.S[uid] = {'lang':'fa','step':'language'}
    app.send(chat, app.TEXT['fa']['lang'], app.lang_menu())

def process(update):
    item = extract_message(update)
    if not item: return
    uid, chat, msg = item
    x = extract_input(msg)
    if x in ('/start','start'):
        reset_start(uid, chat)
        return
    # A second safety net for language labels when a client sends visible text.
    if app.S.get(uid, {}).get('step') == 'language' and x in LABEL_TO_ID:
        x = LABEL_TO_ID[x]
    try:
        app.handle(uid, chat, x)
    except Exception:
        log.exception('Rubika handler error uid=%s chat=%s input=%r', uid, chat, x)
        try:
            app.send(chat, '⚠️ خطای موقت رخ داد. لطفاً دوباره تلاش کنید.', [[('0','❌ انصراف')]])
        except Exception:
            log.exception('Rubika error reply failed')

def main():
    me = api('getMe')
    log.info('Rubika getMe OK: %s', me.get('bot_title') if isinstance(me,dict) else me)
    offset = None
    failures = 0
    while True:
        try:
            payload = {'limit':50}
            if offset:
                payload['offset_id'] = str(offset)
            body = api('getUpdates', payload)
            updates, next_offset = extract_updates(body)
            failures = 0
            if updates:
                log.info('Rubika updates received: %d', len(updates))
                for update in updates:
                    process(update)
            if next_offset:
                offset = str(next_offset)
            else:
                time.sleep(0.4)
        except requests.RequestException as e:
            failures += 1
            log.warning('Rubika API/network error #%s: %s', failures, e)
            time.sleep(min(10, failures * 2))
        except Exception:
            failures += 1
            log.exception('Rubika polling error #%s', failures)
            time.sleep(min(10, failures * 2))

if __name__ == '__main__':
    main()
