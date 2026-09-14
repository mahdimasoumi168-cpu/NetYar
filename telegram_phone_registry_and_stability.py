"""Telegram stability + shared-subscriber phone registry.

Keeps a persistent, deduplicated list of subscriber/customer mobile numbers
collected by services and exposes it from the admin panel.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

PHONE_KEYS = {
    "phone", "gov_phone", "mobile", "subscriber_phone", "customer_phone",
    "irancell_phone", "mobile_number", "customer_mobile", "common_phone",
}

PHONE_MODES = {"govv2_phone", "gov_phone", "government_phone", "gov_phone_input", "irancell_partner_phone"}


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def normalize_phone(v):
    s = re.sub(r"\D", "", _digits(v))
    if s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98"):
        s = "0" + s[2:]
    return s if re.fullmatch(r"09\d{9}", s) else None


def ensure(B):
    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS subscriber_phones(
        phone TEXT PRIMARY KEY,
        first_seen TEXT DEFAULT '',
        last_seen TEXT DEFAULT '',
        use_count INTEGER DEFAULT 1,
        last_service TEXT DEFAULT '',
        last_request_id INTEGER DEFAULT 0
    )""")
    B.db.conn.commit()


def remember(B, phone, service="", request_id=0):
    p = normalize_phone(phone)
    if not p:
        return False
    now = B.db.conn.execute("SELECT datetime('now')").fetchone()[0]
    row = B.db.conn.execute("SELECT phone FROM subscriber_phones WHERE phone=?", (p,)).fetchone()
    if row:
        B.db.conn.execute("""UPDATE subscriber_phones SET last_seen=?,use_count=use_count+1,
            last_service=?,last_request_id=? WHERE phone=?""", (now, service or "", int(request_id or 0), p))
    else:
        B.db.conn.execute("""INSERT INTO subscriber_phones(phone,first_seen,last_seen,use_count,last_service,last_request_id)
            VALUES(?,?,?,?,?,?)""", (p, now, now, 1, service or "", int(request_id or 0)))
    B.db.conn.commit()
    return True


def back_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ پنل مدیریت", callback_data="adm:menu")]])


def install(app, B):
    if getattr(B, "_phone_registry_stability", False):
        return
    ensure(B)

    # Backfill from all existing request answers so the new admin section contains
    # numbers already collected by older services.
    try:
        rows = B.db.conn.execute("""SELECT ra.answer,ra.request_id,r.service_key
            FROM request_answers ra JOIN requests r ON r.id=ra.request_id
            WHERE lower(ra.field_key) IN ('phone','gov_phone','mobile','subscriber_phone','customer_phone','irancell_phone','mobile_number','customer_mobile','common_phone')
            AND trim(ra.answer)<>'' ORDER BY ra.id DESC""").fetchall()
        for r in rows:
            remember(B, r["answer"], r["service_key"], r["request_id"])
    except Exception:
        pass

    async def admin_phones(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        await q.answer()
        rows = B.db.conn.execute("""SELECT phone,use_count,last_service,last_seen,last_request_id
            FROM subscriber_phones ORDER BY last_seen DESC LIMIT 100""").fetchall()
        if not rows:
            text = "📱 شماره موبایل مشترک\n\nهنوز شماره‌ای ثبت نشده است."
        else:
            lines = [f"📱 شماره موبایل مشترک\n\nتعداد شماره‌های یکتا: {len(rows)}\n"]
            for i, r in enumerate(rows, 1):
                svc = r["last_service"] or "-"
                lines.append(f"{i}. 📱 {r['phone']} | دفعات: {int(r['use_count'] or 0)} | خدمت: {svc}")
            text = "\n".join(lines)
        await q.message.reply_text(text[:3900], reply_markup=back_markup())
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(admin_phones, pattern=r"^adm:phones$"), group=-30000000)

    async def phone_guard(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or not msg.text:
            return
        st = B.S.setdefault(user.id, {})
        mode = str(st.get("mode") or "")
        if mode not in PHONE_MODES:
            return
        # Do not compete with the dedicated hotfix for govv2_phone. This guard only
        # records already-validated values when another layer leaves the mode active.
        p = normalize_phone(msg.text)
        if not p:
            return
        if mode.startswith("gov"):
            st["gov_phone"] = p
            st["mode"] = "govv2_dob"
            remember(B, p, "government", 0)
            await msg.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop
        if mode == "irancell_partner_phone":
            st.setdefault("irancell", {})["phone"] = p
            remember(B, p, "irancell_sim_issue", 0)
            st["mode"] = "irancell_partner_document"
            await msg.reply_text("📸 حالا عکس مدرک شناسایی مشترک را ارسال کنید:\n\nمدرک باید واضح و خوانا باشد.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, phone_guard), group=-11000000)
    B._phone_registry_stability = True
