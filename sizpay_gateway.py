"""SizPay gateway integration for NetYar.

Credentials are read only from environment variables:
SIZPAY_MERCHANT_ID, SIZPAY_TERMINAL_ID, SIZPAY_USERNAME, SIZPAY_PASSWORD
Optional: SIZPAY_SIGN_DATA, SIZPAY_SOAP_URL, SIZPAY_PAYMENT_URL.

The Telegram test button creates a 100,000 Toman live payment request.
SizPay's legacy GetToken2 API uses Rial amounts, so 100,000 Toman is sent as 1,000,000 Rial.
"""
import html
import json
import logging
import os
import re
import secrets
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.sizpay")
SOAP_URL = os.getenv("SIZPAY_SOAP_URL", "https://rt.sizpay.ir/KimiaIPGRouteService.asmx").strip()
PAYMENT_URL = os.getenv("SIZPAY_PAYMENT_URL", "https://rt.sizpay.ir/Route/Payment").strip()
SOAP_NS = "https://rt.sizpay.ir"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TEST_AMOUNT_TOMAN = 100_000

def _cfg(name, default=""): return os.getenv(name, default).strip()
def _credentials():
    return {"MerchantID":_cfg("SIZPAY_MERCHANT_ID"),"TerminalID":_cfg("SIZPAY_TERMINAL_ID"),
            "UserName":_cfg("SIZPAY_USERNAME"),"Password":_cfg("SIZPAY_PASSWORD"),"SignData":_cfg("SIZPAY_SIGN_DATA")}
def configured():
    c=_credentials(); return all(c[k] for k in ("MerchantID","TerminalID","UserName","Password"))
def _xml_escape(v): return html.escape(str(v or ""), quote=True)
def _soap(method, params):
    body="".join(f"<{k}>{_xml_escape(v)}</{k}>" for k,v in params.items())
    envelope=(f'<?xml version="1.0" encoding="utf-8"?>'
              f'<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              f'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="{SOAP_ENV}"><soap:Body>'
              f'<{method} xmlns="{SOAP_NS}">{body}</{method}></soap:Body></soap:Envelope>').encode()
    req=urllib.request.Request(SOAP_URL,data=envelope,headers={"Content-Type":"text/xml; charset=utf-8",
        "SOAPAction":f'"{SOAP_NS}/{method}"'},method="POST")
    with urllib.request.urlopen(req,timeout=25) as resp: return resp.read().decode("utf-8","replace")
def _result_json(xml_text, method):
    root=ET.fromstring(xml_text)
    fault=next((e for e in root.iter() if e.tag.lower().endswith("faultstring")),None)
    if fault is not None: raise RuntimeError((fault.text or "SizPay SOAP fault").strip())
    node=next((e for e in root.iter() if e.tag.lower().endswith(method.lower()+"result")),None)
    if node is None: raise RuntimeError("SizPay response did not contain "+method+"Result")
    raw=(node.text or "").strip()
    try: return json.loads(raw)
    except Exception:
        try: return json.loads(html.unescape(raw))
        except Exception: raise RuntimeError("SizPay returned an unreadable result")
def _new_ids(uid):
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"); nonce=secrets.token_hex(4).upper()
    return f"NY{stamp}{nonce}",f"NY-{uid}-{stamp}-{nonce}"
def _return_url():
    base=_cfg("PUBLIC_BASE_URL") or ("https://"+_cfg("RAILWAY_PUBLIC_DOMAIN"))
    if not base: raise RuntimeError("PUBLIC_BASE_URL or RAILWAY_PUBLIC_DOMAIN is required")
    return base.rstrip("/")+"/sizpay/callback"
def _create_token(uid, amount_toman):
    if not configured(): raise RuntimeError("SizPay credentials are not configured")
    c=_credentials(); order_id,invoice_no=_new_ids(uid); rial_amount=int(amount_toman)*10
    data=_result_json(_soap("GetToken2",{"MerchantID":c["MerchantID"],"TerminalID":c["TerminalID"],"Amount":rial_amount,
        "DocDate":"","OrderID":order_id,"ReturnURL":_return_url(),"ExtraInf":f"NetYar Telegram test uid={uid}",
        "InvoiceNo":invoice_no,"AppExtraInf":"","SignData":c["SignData"],"UserName":c["UserName"],"Password":c["Password"]}),"GetToken2")
    code=str(data.get("ResCod",data.get("ResCode",""))).strip(); token=str(data.get("Token","") or "").strip()
    if code not in {"0","00"} or not token: raise RuntimeError(f"SizPay token error: {code or '-'} {str(data.get('Message',data.get('message','خطای سیزپی')) or '').strip()}")
    return order_id,invoice_no,token,rial_amount
def _confirm(token):
    c=_credentials()
    data=_result_json(_soap("Confirm2",{"MerchantID":c["MerchantID"],"TerminalID":c["TerminalID"],"UserName":c["UserName"],
        "Password":c["Password"],"Token":token,"SignData":c["SignData"]}),"Confirm2")
    return str(data.get("ResCod",data.get("ResCode",""))).strip() in {"0","00"},data
def _ensure_table(B):
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS sizpay_transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_user_id INTEGER NOT NULL,order_id TEXT UNIQUE NOT NULL,
        invoice_no TEXT UNIQUE NOT NULL,token TEXT,amount_toman INTEGER NOT NULL,amount_rial INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'created',res_code TEXT,gateway_message TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
    B.db.conn.commit()
def _insert_tx(B,uid,order_id,invoice_no,token,amount_toman,amount_rial):
    now=B.now(); B.db.conn.execute("""INSERT INTO sizpay_transactions
        (telegram_user_id,order_id,invoice_no,token,amount_toman,amount_rial,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)""",(int(uid),order_id,invoice_no,token,int(amount_toman),int(amount_rial),"created",now,now))
    B.db.conn.commit(); return int(B.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
def _safe_text(v,limit=500): return re.sub(r"[\x00-\x1f\x7f]","",str(v or ""))[:limit]
def _pay_page(B,txid):
    row=B.db.conn.execute("SELECT * FROM sizpay_transactions WHERE id=?",(int(txid),)).fetchone()
    if not row: return "<h3>تراکنش پیدا نشد.</h3>"
    if str(row["status"]) in {"paid","cancelled","failed"}: return "<h3>این تراکنش قبلاً پردازش شده است.</h3>"
    c=_credentials()
    inputs="".join(f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(str(v),quote=True)}">'
                   for k,v in {"MerchantID":c["MerchantID"],"TerminalID":c["TerminalID"],"Username":c["UserName"],"Password":c["Password"],"Token":row["token"],"SignData":c["SignData"]}.items())
    return f'''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>درگاه سیزپی</title>
<body style="font-family:tahoma;text-align:center;padding:40px"><h3>در حال انتقال به درگاه سیزپی…</h3>
<p>مبلغ: {int(row["amount_toman"]):,} تومان</p><form id="f" method="post" action="{html.escape(PAYMENT_URL,quote=True)}">{inputs}</form>
<script>document.getElementById("f").submit()</script><noscript><button form="f" type="submit">ورود به درگاه</button></noscript></body></html>'''
def install(app,B):
    if getattr(B,"_sizpay_gateway_installed",False): return True
    _ensure_table(B)
    async def test_callback(update,context):
        q=getattr(update,"callback_query",None)
        if not q or str(q.data or "")!="sizpay:test": return
        uid=int(q.from_user.id)
        try: await q.answer()
        except Exception: pass
        if not configured():
            await q.message.reply_text("❌ درگاه سیزپی تنظیم نشده است.\n\nچهار متغیر SIZPAY_MERCHANT_ID، SIZPAY_TERMINAL_ID، SIZPAY_USERNAME و SIZPAY_PASSWORD را در Railway قرار دهید.")
            raise ApplicationHandlerStop
        try:
            order_id,invoice_no,token,rial=_create_token(uid,TEST_AMOUNT_TOMAN)
            txid=_insert_tx(B,uid,order_id,invoice_no,token,TEST_AMOUNT_TOMAN,rial)
            base=_cfg("PUBLIC_BASE_URL") or ("https://"+_cfg("RAILWAY_PUBLIC_DOMAIN"))
            url=f"{base.rstrip('/')}/sizpay/pay/{txid}"
            await q.message.reply_text("🧪 تست درگاه سیزپی آماده شد.\n\n💰 مبلغ: ۱۰۰٬۰۰۰ تومان\n⚠️ اگر پذیرنده واقعی باشد، پرداخت واقعی است.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 ورود به درگاه سیزپی",url=url)],
                [InlineKeyboardButton("↩️ بازگشت به منوی ایرانی",callback_data="iranian:back")]]))
        except Exception as e:
            log.exception("SizPay token creation failed"); await q.message.reply_text("❌ اتصال سیزپی انجام نشد.\n\n"+_safe_text(e))
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(test_callback,pattern=r"^sizpay:test$"),group=-10000020)
    B._sizpay_gateway_installed=True; log.info("SIZPAY gateway owner installed: test=100000 Toman"); return True
def install_web(api,B):
    if getattr(api,"_sizpay_web_installed",False): return True
    _ensure_table(B)
    from fastapi.responses import HTMLResponse,PlainTextResponse
    @api.get("/sizpay/pay/{txid}")
    async def sizpay_pay(txid:int): return HTMLResponse(_pay_page(B,txid))
    @api.api_route("/sizpay/callback",methods=["GET","POST"])
    async def sizpay_callback(request):
        form={}
        if request.method=="POST":
            try: form.update(dict(await request.form()))
            except Exception: pass
        for k,v in request.query_params.items(): form.setdefault(k,v)
        token=str(form.get("Token") or "").strip(); res_code=str(form.get("ResCod") or form.get("ResCode") or "").strip()
        if not token: return PlainTextResponse("پرداخت سیزپی: توکن دریافت نشد.",status_code=400)
        row=B.db.conn.execute("SELECT * FROM sizpay_transactions WHERE token=? LIMIT 1",(token,)).fetchone()
        if not row: return PlainTextResponse("تراکنش سیزپی پیدا نشد.",status_code=404)
        if str(row["status"])=="paid": return PlainTextResponse("پرداخت قبلاً تأیید شده است.")
        if res_code not in {"0","00"}:
            B.db.conn.execute("UPDATE sizpay_transactions SET status='cancelled',res_code=?,gateway_message=?,updated_at=? WHERE id=?",
                (res_code,_safe_text(form.get("Message")),B.now(),int(row["id"]))); B.db.conn.commit()
            return PlainTextResponse("پرداخت لغو یا ناموفق بود. می‌توانید به ربات برگردید.")
        try: ok,confirmed=_confirm(token)
        except Exception:
            log.exception("SizPay Confirm2 failed"); return PlainTextResponse("پرداخت دریافت شد اما تأیید نهایی ناموفق بود؛ با مدیریت تماس بگیرید.",status_code=502)
        if not ok:
            B.db.conn.execute("UPDATE sizpay_transactions SET status='failed',res_code=?,gateway_message=?,updated_at=? WHERE id=?",
                (str(confirmed.get("ResCod","")), _safe_text(confirmed.get("Message")),B.now(),int(row["id"]))); B.db.conn.commit()
            return PlainTextResponse("تأیید پرداخت سیزپی ناموفق بود.")
        B.db.conn.execute("UPDATE sizpay_transactions SET status='paid',res_code=?,gateway_message=?,updated_at=? WHERE id=?",
            (str(confirmed.get("ResCod","0")),_safe_text(confirmed.get("Message","OK")),B.now(),int(row["id"]))); B.db.conn.commit()
        try:
            app = getattr(B, "_telegram_application", None) or getattr(B, "application", None)
            if app is None: raise RuntimeError("Telegram application is unavailable")
            await app.bot.send_message(chat_id=int(row["telegram_user_id"]),
                text=f"✅ پرداخت سیزپی با موفقیت تأیید شد.\n💰 مبلغ: {int(row['amount_toman']):,} تومان\n🧾 شماره سفارش: {row['order_id']}")
        except Exception: log.exception("SizPay Telegram notification failed")
        return PlainTextResponse("✅ پرداخت با موفقیت تأیید شد. به ربات برگردید.")
    api._sizpay_web_installed=True; log.info("SIZPAY web callback owner installed: /sizpay/callback"); return True
