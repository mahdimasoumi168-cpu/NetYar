import os,sys,time,subprocess,threading
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from app.config import PUBLIC_BASE_URL,RAILWAY_PUBLIC_DOMAIN,SIZPAY_MERCHANT_ID,SIZPAY_TERMINAL_ID
from app.db import init_db,get_payment,set_result
from app.sizpay import confirm,payment_post_html
api=FastAPI(title='NetYar'); children=[]
def public_url(path=''):
 base=(PUBLIC_BASE_URL or (f'https://{RAILWAY_PUBLIC_DOMAIN}' if RAILWAY_PUBLIC_DOMAIN else '')).rstrip('/')
 if not base: raise RuntimeError('Railway public domain is not set')
 return base+path
@api.get('/health')
async def health(): return {'ok':True,'service':'NetYar','telegram':children_alive('telegram'),'rubika':children_alive('rubika')}
def children_alive(name):
 for p,n in children:
  if n==name:return p.poll() is None
 return False
@api.get('/pay/{order_id}',response_class=HTMLResponse)
async def pay(order_id:str):
 row=get_payment(order_id)
 if not row or not row['token']: return HTMLResponse('<h3>سفارش پیدا نشد یا توکن منقضی شده است.</h3>',status_code=404)
 if row['status']!='pending': return HTMLResponse('<h3>این سفارش قبلاً پردازش شده است.</h3>',status_code=409)
 return HTMLResponse(payment_post_html(SIZPAY_MERCHANT_ID,SIZPAY_TERMINAL_ID,row['token']))
async def callback_data(data):
 order_id=data.get('InvoiceNo',''); token=data.get('Token',''); row=get_payment(order_id)
 if not row:return HTMLResponse('<h3>سفارش معتبر نیست.</h3>',status_code=400)
 if row['status']=='paid':return HTMLResponse('<h3>پرداخت قبلاً تأیید شده است.</h3>')
 if data.get('ResCod') not in {'0','00'}:
  set_result(order_id,'failed',data.get('Message','پرداخت ناموفق')); return HTMLResponse('<h3>❌ پرداخت ناموفق یا لغو شد.</h3>')
 if not token:return HTMLResponse('<h3>❌ توکن تراکنش دریافت نشد.</h3>',status_code=400)
 try:
  result=await __import__('asyncio').to_thread(confirm,token); code=str(result.get('ResCod','')).strip(); amount=int(result.get('Amount') or 0)
  if code not in {'0','00'}: set_result(order_id,'failed',result.get('Message','Confirm failed')); return HTMLResponse('<h3>❌ تأیید پرداخت ناموفق بود.</h3>')
  if amount and amount!=int(row['amount_rial']): set_result(order_id,'failed','Amount mismatch'); return HTMLResponse('<h3>❌ مبلغ تراکنش با سفارش مطابقت ندارد.</h3>',status_code=400)
  set_result(order_id,'paid',result.get('Message','پرداخت تأیید شد'),trans_no=result.get('TransNo'),ref_no=result.get('RefNo'),trace_no=result.get('TraceNo'))
  return HTMLResponse('<h2>✅ پرداخت با موفقیت تأیید شد.</h2><p>اکنون به ربات برگردید.</p>')
 except Exception as e:
  set_result(order_id,'error',str(e)[:500]); return HTMLResponse('<h3>❌ خطا در تأیید تراکنش.</h3>',status_code=502)
@api.post('/sizpay/callback')
async def sizpay_callback_post(request:Request): return await callback_data({k:str(v) for k,v in (await request.form()).items()})
@api.get('/sizpay/callback')
async def sizpay_callback_get(request:Request): return await callback_data({k:str(v) for k,v in request.query_params.items()})
def start_child(cmd,name):
 env=os.environ.copy(); env.pop('TELEGRAM_WEBHOOK_URL',None); p=subprocess.Popen([sys.executable,cmd],env=env); children.append((p,name)); return p
def monitor():
 while True:
  time.sleep(5)
  for p,name in list(children):
   if p.poll() is not None:
    try: children.remove((p,name))
    except ValueError: pass
    if name=='telegram' and os.getenv('RUN_TELEGRAM_IN_SERVER','0')!='1': continue
    cmd='telegram_runtime.py' if name=='telegram' else 'rubika_entry_stable.py'
    try: children.append((subprocess.Popen([sys.executable,cmd],env={**os.environ,'TELEGRAM_WEBHOOK_URL':''}),name))
    except Exception: pass
def main():
 init_db()
 # Telegram has a dedicated Worker in this deployment; never start a second getUpdates owner here unless explicitly enabled.
 if os.getenv('RUN_TELEGRAM_IN_SERVER','0')=='1': start_child('telegram_runtime.py','telegram')
 else: logmsg='Telegram polling disabled in NetYar server (dedicated Worker owns Telegram)'; print(logmsg,flush=True)
 start_child('rubika_entry_stable.py','rubika'); threading.Thread(target=monitor,daemon=True).start()
 import uvicorn; uvicorn.run(api,host='0.0.0.0',port=int(os.getenv('PORT','8080')),log_level='info')
if __name__=='__main__': main()
