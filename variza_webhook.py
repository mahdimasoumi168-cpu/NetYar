"""Signed, idempotent Variza payment webhook for NetYar."""
import os, hmac, hashlib, json, logging
from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("netyar.variza")
_REGISTERED = False
VARIZA_AMOUNT_TOLERANCE = 5000


def _register():
    global _REGISTERED
    if _REGISTERED:
        return
    try:
        from server import api
    except Exception:
        return

    @api.post("/variza/webhook")
    async def variza_webhook(request: Request):
        secret = os.getenv("VARIZA_WEBHOOK_SECRET", "").strip()
        if not secret:
            return JSONResponse({"ok": False, "error": "webhook_not_configured"}, status_code=503)
        raw = await request.body()
        signature = request.headers.get("X-Webhook-Signature", "")
        expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return JSONResponse({"ok": False, "error": "invalid_signature"}, status_code=400)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
        if payload.get("event") != "payment.paid" or payload.get("status") != "paid":
            return JSONResponse({"ok": True, "ignored": True})

        import bot as B
        delivery = request.headers.get("X-Delivery-Id", "").strip()
        B.db.conn.execute("CREATE TABLE IF NOT EXISTS variza_deliveries(delivery_id TEXT PRIMARY KEY,created_at TEXT NOT NULL)")
        if delivery and B.db.conn.execute("SELECT 1 FROM variza_deliveries WHERE delivery_id=?", (delivery,)).fetchone():
            return JSONResponse({"ok": True, "duplicate": True})

        slug = str(payload.get("slug") or "").strip()
        try:
            amount = int(payload.get("amount") or 0)
        except Exception:
            amount = 0
        if not slug or amount <= 0:
            return JSONResponse({"ok": False, "error": "invalid_payment"}, status_code=400)

        row = B.db.conn.execute("SELECT r.* FROM requests r JOIN request_answers a ON a.request_id=r.id WHERE a.field_key='variza_slug' AND a.answer=? ORDER BY r.id DESC LIMIT 1", (slug,)).fetchone()
        if not row:
            return JSONResponse({"ok": False, "error": "request_not_found"}, status_code=404)
        rid = int(row["id"])
        expected_amount = int(row["amount"] or 0)
        if abs(amount - expected_amount) > VARIZA_AMOUNT_TOLERANCE:
            log.warning("Variza amount mismatch request=%s expected=%s got=%s", rid, expected_amount, amount)
            return JSONResponse({"ok": False, "error": "amount_mismatch"}, status_code=400)

        if str(row["payment_status"] or "").lower() == "paid":
            if delivery:
                B.db.conn.execute("INSERT OR IGNORE INTO variza_deliveries VALUES(?,?)", (delivery, B.now()))
                B.db.conn.commit()
            return JSONResponse({"ok": True, "already_paid": True})

        B.db.conn.execute("UPDATE requests SET payment_status='paid',payment_method='variza',status='submitted',payment_note=?,updated_at=? WHERE id=? AND payment_status!='paid'", (str(payload.get("attempt_code") or "")[:120], B.now(), rid))
        if delivery:
            B.db.conn.execute("INSERT OR IGNORE INTO variza_deliveries VALUES(?,?)", (delivery, B.now()))
        B.db.conn.commit()

        tracking = str(row["tracking_code"] or "-")
        message = f"✅ پرداخت واریزا تأیید شد\n🎫 کد پیگیری: {tracking}\n💰 مبلغ ثبت‌شده: {amount:,} تومان\n💳 روش: واریزا\n\nاکنون درخواست قابل انجام است."
        try:
            import server
            if server.telegram_app:
                for aid in B.ADM:
                    try:
                        await server.telegram_app.bot.send_message(int(aid), message)
                    except Exception:
                        pass
                user = B.db.conn.execute("SELECT platform,external_id FROM users WHERE id=?", (int(row["user_id"]),)).fetchone()
                if user and user["platform"] == "telegram":
                    try:
                        await server.telegram_app.bot.send_message(int(user["external_id"]), f"✅ پرداخت شما با موفقیت تأیید شد.\n🎫 کد پیگیری: {tracking}\n💰 مبلغ ثبت‌شده: {amount:,} تومان\n\nدرخواست شما اکنون در حال انجام است.")
                    except Exception:
                        pass
        except Exception:
            log.exception("Variza payment notification failed")
        return JSONResponse({"ok": True, "paid": True, "request_id": rid})

    _REGISTERED = True


_register()
