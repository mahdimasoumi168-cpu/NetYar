"""Shared service-invoice helpers with safe per-request Variza links."""
import os, json, urllib.request, urllib.error, logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DEFAULT_PAYMENT_URL = "https://variza.ir/pay/SUUWM6uJzf7BKFzQspaT2"
log = logging.getLogger("netyar.payment")


def _variza_enabled():
    return bool(os.getenv("VARIZA_API_KEY", "").strip())


def _public_return_url():
    """Buyer return URL. Variza webhook URL is configured in the Variza profile."""
    explicit = os.getenv("VARIZA_RETURN_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
        if domain:
            base = "https://" + domain
    return (base + "/payment/return") if base else ""


def _existing_variza(B, tracking_code):
    if not B or not tracking_code:
        return None
    try:
        r = B.db.conn.execute("SELECT id FROM requests WHERE tracking_code=?", (tracking_code,)).fetchone()
        if not r:
            return None
        a = B.db.conn.execute("SELECT field_key,answer FROM request_answers WHERE request_id=? AND field_key IN ('variza_pay_url','variza_slug','variza_amount') ORDER BY id DESC", (int(r["id"]),)).fetchall()
        values = {str(x["field_key"]): str(x["answer"] or "").strip() for x in a}
        return values if values.get("variza_pay_url") and values.get("variza_slug") else None
    except Exception:
        log.exception("failed to read existing Variza payment")
        return None


def create_variza_payment(B, tracking_code, amount, title):
    if not _variza_enabled() or not B or not tracking_code:
        return ""
    try:
        amount = int(amount)
    except Exception:
        return ""
    if amount < 1000:
        log.warning("invalid payment amount: %r", amount)
        return ""

    old = _existing_variza(B, tracking_code)
    if old:
        return old["variza_pay_url"]

    return_url = _public_return_url()
    if not return_url.startswith("https://"):
        log.error("Variza return URL is missing or not HTTPS")
        return ""

    payload = {
        "amount": amount,
        "return_url": return_url,
        "title": str(title or "NetYar Service")[:120],
        "expires_in": os.getenv("VARIZA_PAYMENT_EXPIRES", "2h") or "2h",
    }
    card_last_4 = os.getenv("VARIZA_CARD_LAST_4", "").strip()
    if card_last_4:
        payload["card_last_4"] = card_last_4

    req = urllib.request.Request(
        "https://variza.ir/api/v1/pay",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.getenv("VARIZA_API_KEY", "").strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        url = str(data.get("pay_url") or "").strip()
        slug = str(data.get("slug") or "").strip()
        returned_amount = int(data.get("amount") or amount)
        if not url or not slug or returned_amount != amount:
            log.error("Invalid Variza response for %s: %s", tracking_code, data)
            return ""

        row = B.db.conn.execute("SELECT id FROM requests WHERE tracking_code=?", (tracking_code,)).fetchone()
        if not row:
            log.error("Request not found while saving Variza payment: %s", tracking_code)
            return ""
        rid = int(row["id"])
        B.db.answer(rid, "variza_slug", answer=slug)
        B.db.answer(rid, "variza_pay_url", answer=url)
        B.db.answer(rid, "variza_amount", answer=str(amount))
        B.db.conn.commit()
        return url
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        log.error("Variza API HTTP %s: %s", e.code, body[:1000])
        return ""
    except Exception:
        log.exception("Variza payment creation failed")
        return ""


def payment_url(B=None, tracking_code=None, amount=None, title=None):
    if tracking_code and amount is not None:
        return create_variza_payment(B, tracking_code, amount, title or "NetYar Service")
    value = os.getenv("SERVICE_PAYMENT_URL", "").strip()
    if not value and B is not None:
        try:
            value = B.db.setting("service_payment_url", "").strip()
        except Exception:
            value = ""
    # Never leak a previous customer's payment URL into another invoice.
    if _variza_enabled():
        return ""
    return value or DEFAULT_PAYMENT_URL


def invoice_text(title, amount, tracking_code=None, B=None):
    url = payment_url(B, tracking_code, amount, title)
    lines = [
        f"🧾 <b>{title}</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 مبلغ قابل پرداخت: <b>{int(amount):,} تومان</b>",
    ]
    if tracking_code:
        lines.append(f"🎫 کد پیگیری: <code>{tracking_code}</code>")
    lines.append("━━━━━━━━━━━━━━━━━━")
    if url:
        lines += ["💳 لینک پرداخت:", url, "", "📌 برای پرداخت روی لینک بالا یا دکمه زیر بزنید."]
    elif _variza_enabled():
        lines += ["⚠️ لینک پرداخت ایجاد نشد.", "لطفاً دوباره تلاش کنید یا با مدیریت تماس بگیرید."]
    else:
        lines += ["💳 لینک پرداخت:", payment_url(B), "", "📌 برای پرداخت روی لینک بالا یا دکمه زیر بزنید."]
    lines.append("⏳ پس از تأیید واقعی پرداخت، وضعیت درخواست به‌صورت خودکار تغییر می‌کند.")
    return "\n".join(lines)


def invoice_markup(B=None, tracking_code=None, amount=None, title=None):
    url = payment_url(B, tracking_code, amount, title)
    rows = []
    if url:
        rows.append([InlineKeyboardButton("💳 پرداخت فاکتور", url=url)])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="invoice:cancel")])
    return InlineKeyboardMarkup(rows)

try:
    import variza_webhook  # registers /variza/webhook when server is loaded
except Exception:
    pass
