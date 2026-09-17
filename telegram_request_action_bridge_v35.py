"""Final admin request-action bridge.

Older request notifications in the bot still contain panel:* callbacks. This
layer gives those callbacks a single reliable implementation and redirects
all actions to the same request workflow used by the newer req:* controls.
"""
from __future__ import annotations

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.request_action_bridge_v35")


def _request(B, rid):
    try:
        return B.db.conn.execute(
            "SELECT * FROM requests WHERE id=? LIMIT 1", (int(rid),)
        ).fetchone()
    except Exception:
        log.exception("request lookup failed rid=%s", rid)
        return None


def _markup(rid):
    rid = int(rid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
        [InlineKeyboardButton("💰 تأیید دریافت وجه", callback_data=f"req:pay:{rid}"),
         InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"req:review:{rid}")],
        [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}")],
        [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"),
         InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
        [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"),
         InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
    ])


def _partner_for(B, rid, request_row):
    pid = None
    try:
        cols = {str(x["name"]) for x in B.db.conn.execute(
            "PRAGMA table_info(requests)"
        ).fetchall()}
        if "partner_id" in cols:
            row = B.db.conn.execute(
                "SELECT partner_id FROM requests WHERE id=?",
                (int(rid),),
            ).fetchone()
            if row and row["partner_id"]:
                pid = int(row["partner_id"])
    except Exception:
        pass

    if not pid:
        try:
            row = B.db.conn.execute(
                "SELECT answer FROM request_answers "
                "WHERE request_id=? AND field_key='partner_id' "
                "ORDER BY id DESC LIMIT 1",
                (int(rid),),
            ).fetchone()
            if row and str(row["answer"] or "").strip().isdigit():
                pid = int(row["answer"])
        except Exception:
            pass

    if not pid:
        try:
            raw = str(B.db.setting(f"request_partner_{rid}", "") or "").strip()
            if raw.isdigit():
                pid = int(raw)
        except Exception:
            pass

    candidates = []
    try:
        if pid:
            candidates = B.db.conn.execute(
                "SELECT id,name,phone FROM partners "
                "WHERE id=? AND active=1 LIMIT 1",
                (pid,),
            ).fetchall()
        if not candidates and request_row is not None:
            owner = request_row["user_id"]
            if str(owner or "").strip().isdigit():
                candidates = B.db.conn.execute(
                    "SELECT id,name,phone FROM partners "
                    "WHERE id=? AND active=1 LIMIT 1",
                    (int(owner),),
                ).fetchall()
    except Exception:
        candidates = []

    for p in candidates:
        for key in (f"partner_chat_{p['id']}", f"partner_chat_{p['phone']}"):
            try:
                value = str(B.db.setting(key, "") or "").strip()
                if value and value.lstrip("-").isdigit():
                    return p, int(value)
            except Exception:
                pass
    return (candidates[0], None) if candidates else (None, None)


async def _send_attachments(context, B, admin_id, rid):
    try:
        rows = B.db.conn.execute(
            "SELECT field_key,file_id FROM request_answers "
            "WHERE request_id=? AND file_id!='' ORDER BY id",
            (int(rid),),
        ).fetchall()
    except Exception:
        rows = []

    sent = set()
    for row in rows:
        fid = str(row["file_id"] or "").strip()
        if not fid or fid in sent:
            continue
        sent.add(fid)
        caption = f"📎 {row['field_key']} | درخواست {rid}"
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=fid, caption=caption
            )
        except Exception:
            try:
                await context.bot.send_document(
                    chat_id=admin_id, document=fid, caption=caption
                )
            except Exception:
                log.exception("request attachment send failed rid=%s", rid)


def install(app, B):
    if getattr(B, "_request_action_bridge_v35", False):
        return True

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not B.admin(q.from_user.id):
            return

        data = str(q.data or "")
        if not data.startswith("panel:"):
            return
        parts = data.split(":")
        if len(parts) != 3:
            return

        action = parts[1]
        try:
            rid = int(parts[2])
        except Exception:
            await q.answer("شناسه درخواست نامعتبر است", show_alert=True)
            raise ApplicationHandlerStop

        request_row = _request(B, rid)
        if not request_row:
            await q.answer("درخواست پیدا نشد", show_alert=True)
            raise ApplicationHandlerStop

        try:
            await q.answer()
        except Exception:
            pass

        paid = str(request_row["payment_status"] or "").strip().lower() == "paid"

        if action in {"req", "detail"}:
            answers = B.db.conn.execute(
                "SELECT field_key,answer,file_id FROM request_answers "
                "WHERE request_id=? ORDER BY id",
                (rid,),
            ).fetchall()
            lines = [
                "📋 اطلاعات کامل درخواست",
                "",
                f"🎫 کد پیگیری: {request_row['tracking_code'] or '-'}",
                f"🧾 خدمت: {request_row['service_key'] or '-'}",
                f"📌 وضعیت: {request_row['status'] or '-'}",
                f"💰 مبلغ: {int(request_row['amount'] or 0):,} تومان",
                f"💳 وضعیت پرداخت: {request_row['payment_status'] or '-'}",
                f"💵 روش پرداخت: {request_row['payment_method'] or '-'}",
            ]
            for a in answers:
                value = str(a["answer"] or "").strip()
                if value:
                    lines.append(f"📋 {a['field_key']}: {value}")
                if a["file_id"]:
                    lines.append(f"📎 {a['field_key']}: پیوست موجود است")

            await q.message.reply_text(
                "\n".join(lines), reply_markup=_markup(rid)
            )
            await _send_attachments(context, B, q.from_user.id, rid)
            raise ApplicationHandlerStop

        if action == "askcode":
            partner, chat = _partner_for(B, rid, request_row)
            if not partner:
                await q.message.reply_text(
                    "❌ همکار فعال مرتبط با این درخواست پیدا نشد.",
                    reply_markup=_markup(rid),
                )
                raise ApplicationHandlerStop
            if not chat:
                await q.message.reply_text(
                    "⚠️ همکار پیدا شد، اما چت او ثبت نشده است. "
                    "همکار باید یک‌بار وارد پنل همکاران شود.",
                    reply_markup=_markup(rid),
                )
                raise ApplicationHandlerStop

            B.db.set_setting(f"request_partner_{rid}", str(partner["id"]))
            B.db.conn.execute(
                "UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
            await context.bot.send_message(
                chat_id=chat,
                text=(
                    "🔐 درخواست کد از مدیریت\n"
                    f"🎫 کد پیگیری: {request_row['tracking_code'] or rid}\n"
                    f"🧾 خدمت: {request_row['service_key'] or '-'}\n\n"
                    "لطفاً کد موردنیاز این درخواست را برای مدیریت ارسال کنید."
                ),
            )
            await q.message.reply_text(
                f"📨 درخواست کد برای همکار «{partner['name'] or partner['phone']}» ارسال شد.",
                reply_markup=_markup(rid),
            )
            raise ApplicationHandlerStop

        if action == "review":
            B.db.conn.execute(
                "UPDATE requests SET status='reviewing',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
            await q.message.reply_text(
                "⏳ درخواست وارد بررسی اولیه شد.",
                reply_markup=_markup(rid),
            )
            raise ApplicationHandlerStop

        if action == "approve":
            if not paid:
                await q.message.reply_text(
                    "⛔ ابتدا دریافت وجه را تأیید کنید.",
                    reply_markup=_markup(rid),
                )
                raise ApplicationHandlerStop
            B.db.conn.execute(
                "UPDATE requests SET status='completed',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
            await q.message.reply_text(
                "✅ درخواست تأیید و انجام شد.",
                reply_markup=_markup(rid),
            )
            raise ApplicationHandlerStop

        if action == "reject":
            B.db.conn.execute(
                "UPDATE requests SET status='rejected',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
            await q.message.reply_text(
                "❌ درخواست رد شد.",
                reply_markup=_markup(rid),
            )
            raise ApplicationHandlerStop

        if action == "resend":
            await q.message.reply_text(
                f"📌 درخواست {request_row['tracking_code'] or rid} به آخر چت منتقل شد.",
                reply_markup=_markup(rid),
            )
            await q.message.reply_text(
                f"📋 درخواست {request_row['tracking_code'] or rid}\n"
                f"🧾 خدمت: {request_row['service_key'] or '-'}\n"
                f"📌 وضعیت: {request_row['status'] or '-'}\n"
                f"💰 مبلغ: {int(request_row['amount'] or 0):,} تومان",
                reply_markup=_markup(rid),
            )
            await _send_attachments(context, B, q.from_user.id, rid)
            raise ApplicationHandlerStop

        await q.message.reply_text(
            "⚠️ کنترل قدیمی بود؛ کنترل‌های فعال درخواست جایگزین شدند.",
            reply_markup=_markup(rid),
        )
        raise ApplicationHandlerStop

    app.add_handler(
        CallbackQueryHandler(callback, pattern=r"^panel:"),
        group=-70000,
    )
    B._request_action_bridge_v35 = True
    log.info("Final admin request-action bridge v35 installed")
    return True
