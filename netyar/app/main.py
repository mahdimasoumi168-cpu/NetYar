import asyncio
import os
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from .config import *
from .db import init_db, create_payment, get_payment, set_token, set_result
from .sizpay import get_token, confirm, payment_post_html

app = FastAPI(title='NetYar SIZPay Test')
tg_app = None


def public_url(path=''):
    base = PUBLIC_BASE_URL or (f'https://{RAILWAY_PUBLIC_DOMAIN}' if RAILWAY_PUBLIC_DOMAIN else '')
    if not base:
        raise RuntimeError('Railway public domain is not set. Generate a domain or set PUBLIC_BASE_URL.')
    return base.rstrip('/') + path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton('💳 پرداخت تست — ۱۰۰٬۰۰۰ تومان', callback_data='test_payment')]]
    await update.effective_message.reply_text(
        'سلام 👋\nنت‌یار مهاجر فعال است.\n\nبرای تست اتصال درگاه سیزپی، روی دکمه زیر بزنید:',
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def payment_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    order_id = str(update.effective_user.id) + str(secrets.randbelow(10**10)).zfill(10)
    amount_rial = TEST_AMOUNT_TOMAN * 10
    create_payment(update.effective_user.id, order_id, amount_rial)
    try:
        data = await asyncio.to_thread(get_token, amount_rial, order_id, public_url('/sizpay/callback'))
        token = str(data['Token'])
        invoice = str(data.get('InvoiceNo') or order_id)
        set_token(order_id, token, invoice)
        url = public_url(f'/pay/{order_id}')
        await q.edit_message_text(f'💳 مبلغ تست: ۱۰۰٬۰۰۰ تومان\n\nبرای پرداخت روی لینک زیر بزنید:\n{url}')
    except Exception as e:
        set_result(order_id, 'error', str(e)[:500])
        await q.edit_message_text('❌ ایجاد تراکنش انجام نشد.\n\nخطا: ' + str(e)[:700])


@app.get('/health')
async def health():
    return {'ok': True, 'service': 'NetYar SIZPay Test'}


@app.get('/pay/{order_id}', response_class=HTMLResponse)
async def pay(order_id: str):
    row = get_payment(order_id)
    if not row or not row['token']:
        return HTMLResponse('<h3>سفارش پیدا نشد یا توکن منقضی شده است.</h3>', status_code=404)
    if row['status'] != 'pending':
        return HTMLResponse('<h3>این سفارش قبلاً پردازش شده است.</h3>', status_code=409)
    return HTMLResponse(payment_post_html(SIZPAY_MERCHANT_ID, SIZPAY_TERMINAL_ID, row['token']))


async def _sizpay_callback_data(data):
    order_id = data.get('InvoiceNo','')
    token = data.get('Token','')
    row = get_payment(order_id)
    if not row:
        return HTMLResponse('<h3>سفارش معتبر نیست.</h3>', status_code=400)
    if row['status'] == 'paid':
        return HTMLResponse('<h3>پرداخت قبلاً تأیید شده است. به ربات برگردید.</h3>')
    if data.get('ResCod') not in {'0','00'}:
        set_result(order_id, 'failed', data.get('Message','پرداخت ناموفق'))
        return HTMLResponse('<h3>❌ پرداخت ناموفق یا لغو شد.</h3>')
    if not token:
        set_result(order_id, 'failed', 'Missing Token')
        return HTMLResponse('<h3>❌ توکن تراکنش دریافت نشد.</h3>', status_code=400)
    try:
        result = await asyncio.to_thread(confirm, token)
        code = str(result.get('ResCod','')).strip()
        amount = int(result.get('Amount') or 0)
        if code not in {'0','00'}:
            set_result(order_id, 'failed', result.get('Message','Confirm failed'))
            return HTMLResponse('<h3>❌ تأیید پرداخت ناموفق بود.</h3>')
        if amount and amount != int(row['amount_rial']):
            set_result(order_id, 'failed', 'Amount mismatch')
            return HTMLResponse('<h3>❌ مبلغ تراکنش با سفارش مطابقت ندارد.</h3>', status_code=400)
        set_result(order_id, 'paid', result.get('Message','پرداخت تأیید شد'), trans_no=result.get('TransNo'), ref_no=result.get('RefNo'), trace_no=result.get('TraceNo'))
        return HTMLResponse('<h2>✅ پرداخت با موفقیت تأیید شد.</h2><p>اکنون به ربات نت‌یار برگردید.</p>')
    except Exception as e:
        set_result(order_id, 'error', str(e)[:500])
        return HTMLResponse('<h3>❌ خطا در تأیید تراکنش.</h3>', status_code=502)


async def run():
    global tg_app
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is not set')
    init_db()
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler('start', start))
    tg_app.add_handler(CallbackQueryHandler(payment_button, pattern='^test_payment$'))
    await tg_app.initialize(); await tg_app.start(); await tg_app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)


def main():
    import uvicorn
    init_db()
    async def both():
        server = uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=int(os.getenv('PORT','8080')), log_level='info'))
        await asyncio.gather(run(), server.serve())
    asyncio.run(both())

if __name__ == '__main__':
    main()


@app.post('/sizpay/callback')
async def sizpay_callback_post(request: Request):
    form = await request.form()
    return await _sizpay_callback_data({k: str(v) for k, v in form.items()})


@app.get('/sizpay/callback')
async def sizpay_callback_get(request: Request):
    return await _sizpay_callback_data({k: str(v) for k, v in request.query_params.items()})
