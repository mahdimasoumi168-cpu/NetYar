import json
from datetime import datetime
from typing import Any
import requests
from .config import *

TOKEN_URL = 'https://rt.sizpay.ir/api/PaymentSimple/GetTokenSimple'
CONFIRM_URL = 'https://rt.sizpay.ir/api/PaymentSimple/ConfirmSimple'
PAYMENT_URL = 'https://rt.sizpay.ir/Route/Payment'
PAYLINK_URL = 'https://me.sizpay.ir/{ipg_id}'


def shamsi_today():
    # SIZPay requires Persian date. The gateway documentation explicitly requires YYYY/MM/DD.
    # Avoiding an extra dependency keeps deployment small; install jdatetime only if you want
    # local Persian-date generation. This implementation uses the well-tested algorithm below.
    g = datetime.utcnow().date()
    gy, gm, gd = g.year, g.month, g.day
    # Gregorian -> Jalali (integer algorithm)
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    if gy > 1600:
        jy = 979; gy -= 1600
    else:
        jy = 0; gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400 - 80 + gd + g_d_m[gm-1]
    jy += 33*(days//12053); days %= 12053
    jy += 4*(days//1461); days %= 1461
    if days > 365:
        jy += (days-1)//365; days = (days-1)%365
    if days < 186:
        jm = 1 + days//31; jd = 1 + days%31
    else:
        jm = 7 + (days-186)//30; jd = 1 + (days-186)%30
    return f'{jy:04d}/{jm:02d}/{jd:02d}'


def _check_config():
    missing = [k for k,v in {
        'SIZPAY_USERNAME': SIZPAY_USERNAME,
        'SIZPAY_PASSWORD': SIZPAY_PASSWORD,
        'SIZPAY_MERCHANT_ID': SIZPAY_MERCHANT_ID,
        'SIZPAY_TERMINAL_ID': SIZPAY_TERMINAL_ID,
    }.items() if not v]
    if missing:
        raise RuntimeError('Missing SIZPay environment variables: ' + ', '.join(missing))


def get_token(amount_rial: int, order_id: str, return_url: str, session=requests):
    _check_config()
    payload = {
        'UserName': SIZPAY_USERNAME,
        'Password': SIZPAY_PASSWORD,
        'MerchantID': SIZPAY_MERCHANT_ID,
        'TerminalID': SIZPAY_TERMINAL_ID,
        'Amount': str(int(amount_rial)),
        'DocDate': shamsi_today(),
        'OrderID': str(order_id),
        'ReturnURL': return_url,
        'ExtraInf': 'NetYar test payment',
        'InvoiceNo': str(order_id),
        'AppExtraInf': json.dumps({'Descr':'NetYar test payment'}, ensure_ascii=False),
        'SignData': ''
    }
    r = session.post(TOKEN_URL, json=payload, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    code = str(data.get('ResCod','')).strip()
    if code not in {'0','00'} or not data.get('Token'):
        raise RuntimeError(f"SIZPay token failed: {data.get('Message','unknown')} (code={code})")
    return data


def confirm(token: str, session=requests):
    _check_config()
    payload = {
        'UserName': SIZPAY_USERNAME,
        'Password': SIZPAY_PASSWORD,
        'MerchantID': SIZPAY_MERCHANT_ID,
        'TerminalID': SIZPAY_TERMINAL_ID,
        'Token': token,
        'SignData': ''
    }
    r = session.post(CONFIRM_URL, json=payload, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()


def payment_post_html(merchant_id: str, terminal_id: str, token: str) -> str:
    def esc(s):
        return str(s).replace('&','&amp;').replace('"','&quot;').replace('<','&lt;').replace('>','&gt;')
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>انتقال به سیزپی</title></head><body><p>در حال انتقال به درگاه...</p><form id="f" method="post" action="{PAYMENT_URL}"><input type="hidden" name="MerchantID" value="{esc(merchant_id)}"><input type="hidden" name="TerminalID" value="{esc(terminal_id)}"><input type="hidden" name="Token" value="{esc(token)}"></form><script>document.getElementById('f').submit();</script></body></html>'''
