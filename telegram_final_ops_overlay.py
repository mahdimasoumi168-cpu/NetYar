"""Final Telegram request controls.

Single-purpose final request layer: complete details, attachments, approve,
reject, partner-code request and partner chat. CAPTCHA/checkup controls are
intentionally removed from the product workflow.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.final_ops_overlay")


def install(app, B):
    if getattr(B, "_final_ops_overlay_v3", False):
        return True

    def kb(rid):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
            [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
            [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}")],
            [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
            [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")],
        ])

    def row(rid):
        try:
            return B.db.conn.execute("SELECT * FROM requests WHERE id=?", (int(rid),)).fetchone()
        except Exception:
            return None

    def partner(r):
        try:
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (r["user_id"],)).fetchone()
            if p:
                return p
        except Exception:
            pass
        try:
            mapped = str(B.db.setting(f"request_partner_{r['id']}", "") or "").strip()
            if mapped.isdigit():
                return B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(mapped),)).fetchone()
        except Exception:
            pass
        return None

    def chat_id(p):
        for key in (f"partner_chat_{p['id']}", f"partner_chat_{p['phone']}"):
            try:
                value = str(B.db.setting(key, "") or "").strip()
                if value:
                    return int(value)
            except Exception:
                pass
        return None

    async def send_file(context, aid, fid, caption):
        try:
            await context.bot.send_photo(chat_id=aid, photo=fid, caption=caption)
            return True
        except Exception:
            try:
                await context.bot.send_document(chat_id=aid, document=fid, caption=caption)
                return True
            except Exception:
                return False

    async def cb(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = str(q.data or "")
        if not data.startswith("req:"):
            return
        parts = data.split(":")
        if len(parts) != 3:
            return
        try:
            action = parts[1]
            rid = int(parts[2])
        except Exception:
            await q.answer("درخواست نامعتبر است", show_alert=True)
            raise ApplicationHandlerStop

        r = row(rid)
        if not r:
            await q.answer("درخواست پیدا نشد", show_alert=True)
            raise ApplicationHandlerStop
        await q.answer()

        if action == "v":
            ans = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
            lines = [
                "🔎 اطلاعات کامل درخواست", "",
                f"🎫 کد پیگیری: {r['tracking_code']}",
                f"🧾 خدمت: {r['service_key']}",
                f"📌 وضعیت: {r['status']}",
                f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",
                f"💳 وضعیت پرداخت: {r['payment_status'] or 'تأیید نشده'}",
                f"💵 روش پرداخت: {r['payment_method'] or '-'}",
                f"🕐 تاریخ ثبت: {r['created_at'] or '-'}",
            ]
            for key in r.keys():
                if key in {"id","tracking_code","service_key","status","amount","payment_status","payment_method","created_at","updated_at","language"}:
                    continue
                value = str(r[key] or "").strip()
                if value:
                    lines.append(f"📋 {key}: {value}")
            for a in ans:
                value = str(a["answer"] or "").strip()
                if value:
                    lines.append(f"• {a['field_key']}: {value}")
                if a["file_id"]:
                    lines.append(f"• {a['field_key']}: 📎 پیوست")
            await q.message.reply_text("\n".join(lines), reply_markup=kb(rid))
            sent = set()
            for a in ans:
                fid = a["file_id"]
                if not fid or fid in sent:
                    continue
                sent.add(fid)
                await send_file(context, q.from_user.id, fid, f"📎 {a['field_key']} — درخواست {r['tracking_code']}")
            raise ApplicationHandlerStop

        if action == "a":
            if str(r["payment_status"] or "").lower() != "paid":
                await q.message.reply_text("⛔ ابتدا دریافت وجه را تأیید کنید.", reply_markup=kb(rid))
                raise ApplicationHandlerStop
            B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            await q.message.reply_text("✅ درخواست انجام شد.", reply_markup=kb(rid))
            raise ApplicationHandlerStop

        if action == "x":
            B.db.conn.execute("UPDATE requests SET status='rejected',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            await q.message.reply_text("❌ درخواست رد شد.", reply_markup=kb(rid))
            raise ApplicationHandlerStop

        if action in {"p", "chat"}:
            p = partner(r)
            chat = chat_id(p) if p else None
            if not p or not chat:
                await q.message.reply_text("❌ همکار یا چت همکار برای این درخواست پیدا نشد.", reply_markup=kb(rid))
                raise ApplicationHandlerStop
            B.db.set_setting(f"request_partner_{rid}", str(p["id"]))
            if action == "p":
                await context.bot.send_message(chat_id=chat, text=f"🔐 درخواست کد از همکار\n🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n\nلطفاً کد موردنیاز این درخواست را ارسال کنید.")
                await q.message.reply_text("📨 درخواست کد برای همکار ارسال شد.", reply_markup=kb(rid))
            else:
                await context.bot.send_message(chat_id=chat, text=f"💬 مدیریت ارتباط با شما را برای درخواست {r['tracking_code']} آغاز کرد.")
                await q.message.reply_text("💬 ارتباط با همکار فعال شد.", reply_markup=kb(rid))
            raise ApplicationHandlerStop

        if action == "bottom":
            ans = B.db.conn.execute("SELECT field_key,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
            await q.message.reply_text(f"📌 درخواست {r['tracking_code']} در انتهای چت قرار گرفت.", reply_markup=kb(rid))
            sent = set()
            for a in ans:
                fid = a["file_id"]
                if not fid or fid in sent:
                    continue
                sent.add(fid)
                await send_file(context, q.from_user.id, fid, f"📎 {a['field_key']}")
            raise ApplicationHandlerStop

        if action == "r":
            await q.message.reply_text("✉️ برای پاسخ به این درخواست، پیام خود را ارسال کنید.", reply_markup=kb(rid))
            raise ApplicationHandlerStop

        await q.message.reply_text("این گزینه در این نسخه استفاده نمی‌شود.", reply_markup=kb(rid))
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb, pattern=r"^req:"), group=-50000)
    B._final_ops_overlay_v3 = True
    return True
