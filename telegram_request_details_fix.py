"""Complete Telegram request-details renderer.

Owns the early callback for panel:req so the manager sees every persisted
request answer, including postal code and other service-specific fields.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.request_details")

FIELD_NAMES = {
    "doc_type": "🪪 نوع مدرک",
    "phone": "📱 موبایل مشترک",
    "dob": "🎂 تاریخ تولد",
    "unique_id": "🆔 شناسه یکتا",
    "special_id": "🔖 شناسه اختصاصی",
    "family_code": "👨‍👩‍👧‍👦 کد خانوار",
    "postal_code": "📮 کد پستی منزل",
    "passport": "🛂 شماره/اطلاعات پاسپورت",
    "gov_passport": "🛂 اطلاعات پاسپورت",
    "partner_code": "🔐 کد خدمت",
    "service_code": "🔐 کد خدمت",
    "address": "🏠 نشانی",
    "name": "👤 نام و نام خانوادگی",
    "first_name": "👤 نام",
    "last_name": "👤 نام خانوادگی",
    "national_code": "🆔 کد ملی",
    "tracking_code": "🎫 کد پیگیری",
    "document": "📎 مدرک",
}


def _label(key):
    key = str(key or "").strip()
    if key in FIELD_NAMES:
        return FIELD_NAMES[key]
    return f"📋 {key.replace('_', ' ')}"


def _buttons(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("📤 آوردن درخواست به آخر چت", callback_data=f"panel:resend:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده کامل درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"),
         InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"),
         InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])


async def _show(update, context, B, rid):
    q = update.callback_query
    r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    if not r:
        await q.answer("درخواست پیدا نشد", show_alert=True)
        raise ApplicationHandlerStop

    if not B.admin(q.from_user.id):
        pid = B.S.get(q.from_user.id, {}).get("partner_id")
        if pid != r["user_id"]:
            await q.answer("دسترسی ندارید", show_alert=True)
            raise ApplicationHandlerStop

    answers = B.db.conn.execute(
        "SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",
        (rid,),
    ).fetchall()

    lines = [
        "📋 جزئیات کامل درخواست",
        "",
        f"🎫 کد پیگیری: {r['tracking_code']}",
        f"🧾 خدمت: {r['service_key']}",
        f"📌 وضعیت: {r['status']}",
        f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",
        f"💳 وضعیت پرداخت: {r['payment_status']}",
    ]
    if r["payment_method"]:
        lines.append(f"💵 روش پرداخت: {r['payment_method']}")
    if r["created_at"]:
        lines.append(f"🕐 زمان ثبت: {r['created_at']}")
    lines += ["", "📋 اطلاعات ثبت‌شده:"]

    visible = 0
    for a in answers:
        value = str(a["answer"] or "").strip()
        has_file = bool(a["file_id"])
        if not value and not has_file:
            continue
        label = _label(a["field_key"])
        if value:
            lines.append(f"{label}: {value}")
        elif has_file:
            lines.append(f"{label}: 📎 فایل پیوست دارد")
        visible += 1

    if not visible:
        lines.append("• اطلاعات تکمیلی ثبت نشده است.")

    await q.message.reply_text("\n".join(lines), reply_markup=_buttons(rid))

    for a in answers:
        fid = a["file_id"]
        if not fid:
            continue
        caption = f"📎 {_label(a['field_key'])}"
        try:
            key = str(a["field_key"] or "")
            if key.startswith("file_"):
                await q.message.reply_document(document=fid, caption=caption)
            else:
                # Existing request records use photo file_ids for most identity documents.
                await q.message.reply_photo(photo=fid, caption=caption)
        except Exception:
            try:
                await q.message.reply_document(document=fid, caption=caption)
            except Exception:
                log.exception("request attachment delivery failed: request=%s field=%s", rid, a["field_key"])

    raise ApplicationHandlerStop


async def _callback(update, context, B):
    q = update.callback_query
    data = str(q.data or "")
    if not data.startswith("panel:req:"):
        return
    try:
        rid = int(data.rsplit(":", 1)[1])
    except Exception:
        await q.answer("درخواست نامعتبر است", show_alert=True)
        raise ApplicationHandlerStop
    await q.answer()
    await _show(update, context, B, rid)


def install(app, B):
    if getattr(B, "_telegram_request_details_fix", False):
        return
    # Run before all legacy panel:req handlers so incomplete renderers cannot
    # consume the callback first.
    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^panel:req:"), group=-120)
    B._telegram_request_details_fix = True
