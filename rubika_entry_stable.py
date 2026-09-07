import os,time,logging,requests
import rubika_v2 as bot
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s')
log=logging.getLogger('netyar.rubika.stable')
TOKEN=os.getenv('RUBIKA_BOT_TOKEN','').strip()
ADM={x.strip() for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip()}
ADMIN_COMMAND=os.getenv('ADMIN_COMMAND','/Admin2025').strip().lower()

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
                        bot.send(chat,'⛔ دسترسی مدیریت ندارید.')
                        continue
                    bot.process(u)
                except Exception:
                    log.exception('Rubika update failed')
            if nxt is not None:offset=str(nxt)
            time.sleep(.25 if updates else .8)
        except requests.RequestException as e:
            log.warning('Rubika network/API error: %s',e);time.sleep(3)
        except Exception:
            log.exception('Rubika polling error');time.sleep(3)
if __name__=='__main__':main()
