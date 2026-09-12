"""Exact per-partner pricing flow.

The admin supplies the final price directly. No percentage, delta or automatic
calculation is used. Sending 0 removes the special price and restores the
public service price.
"""
import re
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def _save(db, partner_id, service_key, value):
    if value == 0:
        db.conn.execute(
            "DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",
            (partner_id, service_key),
        )
    else:
        db.conn.execute(
            "INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",
            (partner_id, service_key, value, _now()),
        )
    db.conn.commit()


def install_telegram(app, B):
    try:
        from telegram.ext import MessageHandler, filters
        if getattr(B, "_partner_price_exact_tg", False):
            return
        async def handler(update, context):
            if not update.message or not B.admin(update.effective_user.id):
                return
            st = B.S.setdefault(update.effective_user.id, {})
            mode = st.get("mode")
            text = (update.message.text or "").strip()
            if mode == "pp_service" and st.get("pp_partner_id"):
                key = text.split("|")[0].strip()
                r = B.db.conn.execute("SELECT key,name,price FROM services WHERE key=?", (key,)).fetchone()
                if not r:
                    return await update.message.reply_text("❌ کلید خدمت پیدا نشد. کلید درست خدمت را ارسال کنید.")
                st["pp_service_key"] = key
                st["pp_current_price"] = int(r["price"] or 0)
                st["mode"] = "pp_exact_value"
                return await update.message.reply_text(
                    f"💰 {r['name']}\n"
                    f"قیمت عمومی: {int(r['price'] or 0):,} تومان\n\n"
                    "قیمت نهایی این همکار را دقیقاً به تومان وارد کنید.\n"
                    "مثلاً: 420000\n"
                    "برای حذف قیمت ویژه و برگشت به قیمت عمومی: 0"
                )
            if mode == "pp_exact_value" and st.get("pp_partner_id") and st.get("pp_service_key"):
                raw = re.sub(r"[٬,\s]", "", text)
                if not raw.isdigit():
                    return await update.message.reply_text("❌ فقط عدد وارد کنید؛ مثال: 420000")
                value = int(raw)
                _save(B.db, int(st["pp_partner_id"]), st["pp_service_key"], value)
                st["mode"] = None
                msg = "🗑 قیمت ویژه حذف شد و قیمت عمومی فعال شد." if value == 0 else f"✅ قیمت ویژه همکار دقیقاً روی {value:,} تومان ثبت شد."
                return await update.message.reply_text(msg + "\n👤 این قیمت فقط برای همین همکار است.")
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-8)
        B._partner_price_exact_tg = True
    except Exception:
        import logging
        logging.getLogger("netyar.partner_price_exact").exception("Telegram exact pricing install failed")


def install_rubika(R):
    try:
        if getattr(R, "_partner_price_exact_rb", False):
            return
        old_admin = R.admin
        def admin(uid, chat, x):
            uid = str(uid)
            st = R.STATE.setdefault(uid, {})
            text = str(x or "").strip()
            if st.get("step") == "pp_service" and st.get("pp_partner_id"):
                key = text.split("|")[0].strip()
                r = R.db.conn.execute("SELECT key,name,price FROM services WHERE key=?", (key,)).fetchone()
                if not r:
                    return R.send(chat, "❌ کلید خدمت پیدا نشد.")
                st["pp_service_key"] = key
                st["pp_current_price"] = int(r["price"] or 0)
                st["step"] = "pp_exact_value"
                return R.send(chat, f"💰 {r['name']}\nقیمت عمومی: {int(r['price'] or 0):,} تومان\n\nقیمت نهایی این همکار را دقیقاً به تومان وارد کنید.\nمثال: 420000\nبرای حذف قیمت ویژه: 0", [[("0", "❌ انصراف")]])
            if st.get("step") == "pp_exact_value" and st.get("pp_partner_id") and st.get("pp_service_key"):
                raw = re.sub(r"[٬,\s]", "", text)
                if not raw.isdigit():
                    return R.send(chat, "❌ فقط عدد وارد کنید؛ مثال: 420000")
                value = int(raw)
                _save(R.db, int(st["pp_partner_id"]), st["pp_service_key"], value)
                st["step"] = "admin"
                msg = "🗑 قیمت ویژه حذف شد و قیمت عمومی فعال شد." if value == 0 else f"✅ قیمت ویژه همکار دقیقاً روی {value:,} تومان ثبت شد."
                return R.send(chat, msg + "\n👤 این قیمت فقط برای همین همکار است.", R.admin_rows())
            return old_admin(uid, chat, x)
        R.admin = admin
        R._partner_price_exact_rb = True
    except Exception:
        import logging
        logging.getLogger("netyar.partner_price_exact").exception("Rubika exact pricing install failed")
