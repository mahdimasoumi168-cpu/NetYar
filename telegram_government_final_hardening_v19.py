"""Final Government service hardening v19.

One authoritative layer for:
- unique-id validation (exactly 10 digits, starts with 9) across all known
  government state machines;
- paid-request deduplication by exclusive/special ID;
- atomic partner-balance charging for the legacy govv2 photo-submit path;
- complete admin notifications with all request attachments and practical
  review/approve/reject/chat controls.
"""
import logging
import re
import secrets

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.gov_hardening_v19")
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789")
UNIQUE_MODES = {"gov_unique", "govv2_unique", "govf_unique", "govv3_unique"}
PHOTO_MODE = "govv2_photo"
SERVICE_KEY = "government"


def digits(value):
    return str(value or "").translate(DIGITS).strip()


def unique_valid(value):
    return bool(re.fullmatch(r"9\d{9}", digits(value)))


def special_valid(value):
    return bool(re.fullmatch(r"1\d{11}", digits(value)))


def _admin_ids(B):
    raw = getattr(B, "ADM", None) or getattr(B, "ADMINS", None) or ()
    if isinstance(raw, (str, int)):
        raw = (raw,)
    out = []
    for x in raw:
        try:
            out.append(int(x))
        except Exception:
            pass
    return list(dict.fromkeys(out))


def _partner_ids(B):
    # No implicit admin/partner relation; this is only a helper for safe checks.
    return None


def _find_paid_by_special(B, owner, special):
    special = digits(special)
    if not special:
        return None
    try:
        return B.db.conn.execute(
            """
            SELECT r.id, r.tracking_code
            FROM requests r
            JOIN request_answers a ON a.request_id=r.id
            WHERE r.user_id=?
              AND r.service_key=?
              AND r.payment_status='paid'
              AND a.field_key IN ('special_id','gov_special')
              AND a.answer=?
            ORDER BY r.id DESC
            LIMIT 1
            """,
            (owner, SERVICE_KEY, special),
        ).fetchone()
    except Exception:
        log.exception("paid-by-special lookup failed")
        return None


def _all_files(B, rid):
    files = []
    seen = set()
    try:
        rows = B.db.conn.execute(
            "SELECT field_key,file_id FROM request_answers WHERE request_id=? AND COALESCE(file_id,'')!='' ORDER BY id",
            (int(rid),),
        ).fetchall()
        for row in rows:
            fid = str(row["file_id"] or "").strip()
            if fid and fid not in seen:
                files.append((str(row["field_key"] or "فایل"), fid, "photo"))
                seen.add(fid)
    except Exception:
        log.exception("request_answers attachment lookup failed")
    try:
        rows = B.db.conn.execute(
            "SELECT file_id,file_type,caption FROM request_files WHERE request_id=? ORDER BY id",
            (int(rid),),
        ).fetchall()
        for row in rows:
            fid = str(row["file_id"] or "").strip()
            if not fid or fid in seen:
                continue
            kind = str(row["file_type"] or "photo").lower()
            label = str(row["caption"] or "فایل درخواست")
            files.append((label, fid, "document" if "doc" in kind or "file" in kind else "photo"))
            seen.add(fid)
    except Exception:
        # request_files is an optional compatibility table.
        pass
    return files


def _controls(rid, paid):
    rows = [
        [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"rq:detail:{rid}")],
        [InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"rq:review:{rid}")],
    ]
    if paid:
        rows.append([InlineKeyboardButton("✅ تأیید انجام خدمت", callback_data=f"rq:approve:{rid}"), InlineKeyboardButton("❌ رد درخواست", callback_data=f"rq:reject:{rid}")])
    else:
        rows.append([InlineKeyboardButton("💰 تأیید دریافت وجه", callback_data=f"rq:payconfirm:{rid}"), InlineKeyboardButton("❌ رد درخواست", callback_data=f"rq:reject:{rid}")])
    rows.append([InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"rq:ask:{rid}")])
    rows.append([InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")])
    return InlineKeyboardMarkup(rows)


def _request_text(B, rid, extra=""):
    row = B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1", (int(rid),)).fetchone()
    if not row:
        return None
    lines = [
        "🆕 درخواست جدید دولت من",
        f"🎫 کد پیگیری: {row['tracking_code']}",
        "🧾 خدمت: حل مشکل سامانه دولت من",
        f"📌 وضعیت: {row['status'] or '-'}",
        f"💰 مبلغ: {int(row['amount'] or 0):,} تومان",
        f"💳 پرداخت: {row['payment_status'] or '-'}",
        f"💵 روش پرداخت: {row['payment_method'] or '-'}",
    ]
    try:
        answers = B.db.conn.execute(
            "SELECT field_key,answer FROM request_answers WHERE request_id=? AND COALESCE(answer,'')!='' ORDER BY id",
            (int(rid),),
        ).fetchall()
        labels = {
            "doc_type": "🪪 نوع مدرک",
            "phone": "📱 شماره موبایل مشترک",
            "gov_phone": "📱 شماره موبایل مشترک",
            "dob": "🎂 تاریخ تولد مشترک",
            "gov_dob": "🎂 تاریخ تولد مشترک",
            "unique_id": "🆔 شناسه یکتای مشترک",
            "gov_unique": "🆔 شناسه یکتای مشترک",
            "special_id": "🔖 شناسه اختصاصی مشترک",
            "gov_special": "🔖 شناسه اختصاصی مشترک",
            "family_code": "👨‍👩‍👧‍👦 کد خانوار مشترک",
            "gov_family_code": "👨‍👩‍👧‍👦 کد خانوار مشترک",
            "postal_code": "📮 کد پستی مشترک",
            "gov_postal": "📮 کد پستی مشترک",
            "passport": "🛂 شماره پاسپورت مشترک",
            "booklet_number": "📗 شماره دفترچه اقامت مشترک",
            "partner_id": "👤 شناسه همکار",
            "requester_telegram_id": "🆔 شناسه تلگرام درخواست‌دهنده",
        }
        for a in answers:
            k = str(a["field_key"] or "")
            v = str(a["answer"] or "").strip()
            if v:
                lines.append(f"{labels.get(k, '📋 ' + k)}: {v}")
    except Exception:
        log.exception("request answer lookup failed")
    if extra:
        lines.extend(["", extra])
    return "\n".join(lines)


async def _notify_admins(B, application, rid, note=""):
    text = _request_text(B, rid, note)
    if not text:
        return False
    row = B.db.conn.execute("SELECT payment_status FROM requests WHERE id=?", (int(rid),)).fetchone()
    paid = bool(row and str(row["payment_status"] or "") == "paid")
    kb = _controls(rid, paid)
    files = _all_files(B, rid)
    ok = True
    for aid in _admin_ids(B):
        try:
            await application.bot.send_message(chat_id=aid, text=text, reply_markup=kb)
        except Exception:
            ok = False
            log.exception("admin request message failed rid=%s aid=%s", rid, aid)
        for label, fid, kind in files:
            try:
                caption = f"📎 {label}\n🎫 {rid}"
                if kind == "document":
                    await application.bot.send_document(chat_id=aid, document=fid, caption=caption)
                else:
                    await application.bot.send_photo(chat_id=aid, photo=fid, caption=caption)
            except Exception:
                try:
                    await application.bot.send_document(chat_id=aid, document=fid, caption=caption)
                except Exception:
                    ok = False
                    log.exception("admin attachment failed rid=%s aid=%s", rid, aid)
    return ok


def _insert_request(B, owner, amount):
    code = "NYM-" + secrets.token_hex(4).upper()
    now = B.now()
    cur = B.db.conn.execute(
        "INSERT INTO requests(tracking_code,user_id,service_key,platform,status,amount,payment_status,payment_method,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (code, owner, SERVICE_KEY, "telegram", "awaiting_payment", int(amount), "unpaid", "", now, now),
    )
    return cur.lastrowid, code


def _field_values(st):
    typ = st.get("gov_doc_type")
    values = [
        ("doc_type", typ),
        ("phone", st.get("gov_phone")),
        ("dob", st.get("gov_dob")),
        ("unique_id", st.get("gov_unique")),
        ("special_id", st.get("gov_special")),
        ("postal_code", st.get("gov_postal")),
    ]
    if typ in {"card", "temporary_card"}:
        values.append(("family_code", st.get("gov_family_code")))
    elif typ == "passport":
        values.append(("passport", st.get("gov_identity_number")))
    elif typ == "residence_booklet":
        values.append(("booklet_number", st.get("gov_identity_number")))
    return [(k, str(v)) for k, v in values if v not in (None, "")]


def _file_fields(st, fid):
    # govv2_photo is the final required document for this path.
    return [("document", fid)]


def install(app, B):
    if getattr(B, "_gov_final_hardening_v19", False):
        return True

    async def strict_unique(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not getattr(msg, "text", None):
            return
        st = B.S.setdefault(user.id, {})
        mode = str(st.get("mode") or "")
        if mode not in UNIQUE_MODES:
            return
        value = digits(msg.text)
        if not unique_valid(value):
            await msg.reply_text("❌ شناسه یکتا نامعتبر است.\n🆔 باید دقیقاً ۱۰ رقم باشد و با ۹ شروع شود.")
            raise ApplicationHandlerStop

    async def final_govv2_media(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user:
            return
        st = B.S.setdefault(user.id, {})
        if st.get("mode") != PHOTO_MODE:
            return
        fid = msg.photo[-1].file_id if getattr(msg, "photo", None) else (msg.document.file_id if getattr(msg, "document", None) else "")
        if not fid:
            return
        amount = int(B.db.setting("price_government", "500000") or 500000)
        pid = st.get("partner_id")
        owner = pid or B.db.user("telegram", user.id, user.username or "", user.full_name or "")
        typ = st.get("gov_doc_type")
        special = digits(st.get("gov_special"))
        if not unique_valid(st.get("gov_unique")) or not special_valid(special):
            await msg.reply_text("❌ اطلاعات هویتی ناقص یا نامعتبر است. لطفاً خدمت را از ابتدا انجام دهید.", reply_markup=B.partner_kb("fa") if pid else B.main(user.id))
            st["mode"] = None
            raise ApplicationHandlerStop

        conn = B.db.conn
        rid = None
        code = None
        duplicate = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            duplicate = _find_paid_by_special(B, owner, special)
            amount_to_charge = 0 if duplicate else amount
            rid, code = _insert_request(B, owner, amount_to_charge)
            for key, value in _field_values(st):
                B.db.answer(rid, key, answer=value)
            for key, file_id in _file_fields(st, fid):
                B.db.answer(rid, key, file_id=file_id)
            B.db.answer(rid, "requester_telegram_id", answer=str(user.id))
            if pid and duplicate:
                conn.execute(
                    "UPDATE requests SET status='submitted',payment_status='paid',payment_method='previous_government_request',payment_note=?,updated_at=? WHERE id=?",
                    (f"هزینه قبلاً برای شناسه اختصاصی {special} پرداخت شده است؛ درخواست مجدد بدون کسر هزینه. کد قبلی: {duplicate['tracking_code']}", B.now(), rid),
                )
            elif pid:
                row = conn.execute("SELECT balance,active FROM partners WHERE id=? LIMIT 1", (int(pid),)).fetchone()
                balance = int(row["balance"] or 0) if row else 0
                if not row or not row["active"] or balance < amount:
                    raise RuntimeError("insufficient_partner_balance")
                cur = conn.execute(
                    "UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND active=1 AND balance>=?",
                    (amount, B.now(), int(pid), amount),
                )
                if cur.rowcount != 1:
                    raise RuntimeError("insufficient_partner_balance")
                conn.execute(
                    "UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",
                    (B.now(), rid),
                )
            else:
                if duplicate:
                    conn.execute(
                        "UPDATE requests SET status='submitted',payment_status='paid',payment_method='previous_government_request',payment_note=?,updated_at=? WHERE id=?",
                        (f"هزینه قبلاً برای شناسه اختصاصی {special} پرداخت شده است؛ درخواست مجدد بدون پرداخت مجدد. کد قبلی: {duplicate['tracking_code']}", B.now(), rid),
                    )
                else:
                    conn.execute(
                        "UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='card_to_card',updated_at=? WHERE id=?",
                        (B.now(), rid),
                    )
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            log.exception("final govv2 submit failed")
            if rid:
                try:
                    conn.execute("DELETE FROM requests WHERE id=?", (int(rid),)); conn.commit()
                except Exception:
                    pass
            if str(exc) == "insufficient_partner_balance":
                row = conn.execute("SELECT balance FROM partners WHERE id=?", (int(pid),)).fetchone() if pid else None
                bal = int(row["balance"] or 0) if row else 0
                await msg.reply_text(
                    f"❌ اعتبار پنل همکاران کافی نیست.\n\n💳 اعتبار فعلی: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان\n\nابتدا حساب همکار را شارژ کنید.",
                    reply_markup=B.partner_kb("fa") if pid else B.main(user.id),
                )
            else:
                await msg.reply_text("❌ ثبت درخواست انجام نشد و مبلغی کسر نشد.", reply_markup=B.partner_kb("fa") if pid else B.main(user.id))
            st["mode"] = None
            raise ApplicationHandlerStop

        st["mode"] = None
        if duplicate:
            note = f"🔁 درخواست مجدد با شناسه اختصاصی تکراری؛ هیچ هزینه جدیدی کسر نشد.\n📌 کد قبلی: {duplicate['tracking_code']}"
        elif pid:
            note = "💳 هزینه از اعتبار پنل همکار کسر شد."
        else:
            note = "💳 این درخواست در انتظار پرداخت کارت‌به‌کارت است."
        await _notify_admins(B, context.application, rid, note)

        if pid:
            if duplicate:
                reply = f"✅ درخواست مجدد ثبت شد.\n🎫 کد پیگیری: {code}\n🔁 هزینه جدید: ۰ تومان\n📌 هزینه قبلاً برای این شناسه اختصاصی پرداخت شده است."
            else:
                reply = f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💳 {amount:,} تومان از اعتبار پنل کسر شد."
            await msg.reply_text(reply, reply_markup=B.partner_kb(st.get("lang", "fa")))
        else:
            if duplicate:
                await msg.reply_text(f"✅ درخواست مجدد ثبت شد.\n🎫 کد پیگیری: {code}\n💰 هزینه جدید: ۰ تومان", reply_markup=B.main(user.id))
            else:
                card = getattr(B, "db", None).setting("card_number", "") or ""
                owner_name = getattr(B, "db", None).setting("card_owner", "") or ""
                await msg.reply_text(
                    f"🧾 فاکتور حل مشکل سامانه دولت من\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان\n💳 شماره کارت: {card or 'در تنظیمات ثبت نشده'}\n👤 به نام: {owner_name or '-'}\n\nپس از کارت‌به‌کارت، عکس رسید را ارسال کنید.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]]),
                )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, strict_unique), group=-400000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, final_govv2_media), group=-12000)
    B._gov_final_hardening_v19 = True
    log.info("Government final hardening v19 installed: unique=9xxxxxxxxx, special-ID dedup, atomic billing, complete admin attachments")
    return True
