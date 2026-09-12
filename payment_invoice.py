"""Shared service-invoice helpers with safe per-request Variza links."""
import os, json, urllib.request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DEFAULT_PAYMENT_URL = "https://variza.ir/pay/SUUWM6uJzf7BKFzQspaT2"
_LAST_PAYMENT_URL = ""


def _variza_enabled():
    return bool(os.getenv("VARIZA_API_KEY", "").strip())


def _public_return_url():
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if domain:
            base = "https://" + domain
    return (os.getenv("VARIZA_RETURN_URL", "").strip().rstrip("/") or base) + "/health" if (os.getenv("VARIZA_RETURN_URL", "").strip() or base) else ""


def _existing_variza_url(B, tracking_code):
    if not B or not tracking_code:
        return ""
    try:
        r = B.db.conn.execute("SELECT id FROM requests WHERE tracking_code=?", (tracking_code,)).fetchone()
        if not r:
            return ""
        a = B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='variza_pay_url' ORDER BY id DESC LIMIT 1", (int(r["id"]),)).fetchone()
        return str(a["answer"] or "").strip() if a else ""
    except Exception:
        return ""


def create_variza_payment(B, tracking_code, amount, title):
    global _LAST_PAYMENT_URL
    if not _variza_enabled():
        return ""
    old = _existing_variza_url(B, tracking_code)
    if old:
        _LAST_PAYMENT_URL = old
        return old
    callback = _public_return_url()
    if not callback:
        return ""
    payload = {"amount": int(amount), "return_url": callback, "title": str(title or "NetYar Service")[:120], "expires_in": os.getenv("VARIZA_PAYMENT_EXPIRES", "2h") or "2h"}
    req = urllib.request.Request("https://variza.ir/api/v1/pay", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": "Bearer " + os.getenv("VARIZA_API_KEY", "").strip(), "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        url, slug = str(data.get("pay_url") or "").strip(), str(data.get("slug") or "").strip()
        if not url or not slug:
            return ""
        r = B.db.conn.execute("SELECT id FROM requests WHERE tracking_code=?", (tracking_code,)).fetchone()
        if r:
            B.db.answer(int(r["id"]), "variza_slug", answer=slug)
            B.db.answer(int(r["id"]), "variza_pay_url", answer=url)
            B.db.answer(int(r["id"]), "variza_amount", answer=str(int(amount)))
            B.db.conn.commit()
        _LAST_PAYMENT_URL = url
        return url
    except Exception:
        return ""


def payment_url(B=None, tracking_code=None, amount=None, title=None):
    global _LAST_PAYMENT_URL
    if tracking_code and amount is not None:
        url = create_variza_payment(B, tracking_code, amount, title or "NetYar Service")
        if url:
            return url
    if _LAST_PAYMENT_URL:
        return _LAST_PAYMENT_URL
    value = os.getenv("SERVICE_PAYMENT_URL", "").strip()
    if not value and B is not None:
        try:
            value = B.db.setting("service_payment_url", "").strip()
        except Exception:
            value = ""
    if _variza_enabled() and not value:
        return ""
    return value or DEFAULT_PAYMENT_URL


def invoice_text(title, amount, tracking_code=None, B=None):
    url = payment_url(B, tracking_code, amount, title)
    lines = [f"🧾 <b>{title}</b>", "━━━━━━━━━━━━━━━━━━", f"💰 مبلغ قابل پرداخت: <b>{int(amount):,} تومان</b>"]
    if tracking_code:
        lines.append(f"🎫 کد پیگیری: <code>{tracking_code}</code>")
    lines.append("━━━━━━━━━━━━━━━━━━")
    if url:
        lines += ["💳 لینک پرداخت:", url, "", "📌 برای پرداخت روی لینک بالا یا دکمه زیر بزنید."]
    elif _variza_enabled():
        lines += ["⚠️ لینک پرداخت خودکار فعلاً ساخته نشد.", "لطفاً دوباره تلاش کنید یا با مدیریت تماس بگیرید."]
    else:
        lines += ["💳 لینک پرداخت:", payment_url(B), "", "📌 برای پرداخت روی لینک بالا یا دکمه زیر بزنید."]
    lines += ["⏳ پس از تأیید واقعی پرداخت، وضعیت درخواست به‌صورت خودکار تغییر می‌کند."]
    return "\n".join(lines)


def invoice_markup(B=None):
    url = payment_url(B)
    rows = []
    if url:
        rows.append([InlineKeyboardButton("💳 پرداخت فاکتور", url=url)])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="invoice:cancel")])
    return InlineKeyboardMarkup(rows)

try:
    import variza_webhook  # registers /variza/webhook when server is loaded
except Exception:
    pass
