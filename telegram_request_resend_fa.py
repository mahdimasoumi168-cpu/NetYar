"""Persian renderer for the 'bring request to end of chat' action."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

FIELD_NAMES = {
    "doc_type": "🪪 نوع مدرک",
    "phone": "📱 موبایل مشترک",
    "dob": "🎂 تاریخ تولد",
    "unique_id": "🆔 شناسه یکتا",
    "special_id": "🔖 شناسه اختصاصی",
    "family_code": "👨‍👩‍👧‍👦 کد خانوار",
    "postal_code": "📮 کد پستی منزل",
    "passport": "🛂 اطلاعات پاسپورت",
    "gov_passport": "🛂 اطلاعات پاسپورت",
    "booklet_number": "📗 شماره دفترچه اقامت",
    "address": "🏠 نشانی",
    "name": "👤 نام و نام خانوادگی",
    "first_name": "👤 نام",
    "last_name": "👤 نام خانوادگی",
    "national_code": "🆔 کد ملی",
    "document": "🪪 تصویر مدرک شناسایی",
    "sim_card_document": "📱 تصویر سند سیم‌کارت (اختیاری)",
}

SERVICE_NAMES = {
    "government": "حل مشکل سامانه دولت من اتباع",
    "fida": "خدمات فیدای غیرحضوری",
    "print": "خدمات چاپ",
}
STATUS_NAMES = {
    "new": "جدید",
    "awaiting_payment": "در انتظار پرداخت",
    "submitted": "ثبت شده",
    "review": "در حال بررسی",
    "approved": "انجام شد",
    "rejected": "رد شده",
    "cancelled": "لغو شده",
}
PAYMENT_NAMES = {"paid": "پرداخت شده", "unpaid": "پرداخت نشده", "pending": "در انتظار پرداخت"}
METHOD_NAMES = {"partner_balance": "اعتبار همکار", "previous_government_request": "درخواست قبلی دولت من"}


def _label(key):
    key = str(key or "").strip()
    return FIELD_NAMES.get(key, f"📋 {key.replace('_', ' ')}")


def _buttons(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("📤 آوردن درخواست به آخر چت", callback_data=f"panel:resend:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده کامل درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"), InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"), InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])


async def _resend(update, context, B, rid):
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
        "SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)
    ).fetchall()
    service = SERVICE_NAMES.get(str(r["service_key"]), str(r["service_key"]))
    status = STATUS_NAMES.get(str(r["status"]), str(r["status"]))
    payment = PAYMENT_NAMES.get(str(r["payment_status"]), str(r["payment_status"]))
    method = METHOD_NAMES.get(str(r["payment_method"]), str(r["payment_method"]))

    lines = [
        "📌 درخواست در انتهای چت",
        "",
        f"🎫 کد پیگیری: {r['tracking_code']}",
        f"🧾 خدمت: {service}",
        f"📌 وضعیت: {status}",
        f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",
        f"💳 وضعیت پرداخت: {payment}",
    ]
    if method:
        lines.append(f"💵 روش پرداخت: {method}")
    if r["created_at"]:
        lines.append(f"🕐 زمان ثبت: {r['created_at']}")
    lines += ["", "📋 اطلاعات درخواست:"]

    for a in answers:
        value = str(a["answer"] or "").strip()
        if value:
            lines.append(f"{_label(a['field_key'])}: {value}")
        elif a["file_id"] and a["field_key"] in FIELD_NAMES:
            lines.append(f"{_label(a['field_key'])}: 📎 پیوست شده")

    await q.message.reply_text("\n".join(lines), reply_markup=_buttons(rid))
    for a in answers:
        fid = a["file_id"]
        if not fid:
            continue
        caption = f"📎 {_label(a['field_key'])}"
        try:
            if str(a["field_key"]).startswith("file_"):
                await q.message.reply_document(document=fid, caption=caption)
            else:
                await q.message.reply_photo(photo=fid, caption=caption)
        except Exception:
            try:
                await q.message.reply_document(document=fid, caption=caption)
            except Exception:
                pass
    raise ApplicationHandlerStop


async def _callback(update, context, B):
    q = update.callback_query
    data = str(q.data or "")
    if not data.startswith("panel:resend:"):
        return
    try:
        rid = int(data.rsplit(":", 1)[1])
    except Exception:
        await q.answer("درخواست نامعتبر است", show_alert=True)
        raise ApplicationHandlerStop
    await q.answer()
    await _resend(update, context, B, rid)


def install(app, B):
    if getattr(B, "_telegram_request_resend_fa", False):
        return
    app.add_handler(CallbackQueryHandler(lambda u, c: _callback(u, c, B), pattern=r"^panel:resend:"), group=-121)
    B._telegram_request_resend_fa = True
