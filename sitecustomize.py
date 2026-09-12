"""Small, non-invasive startup compatibility hooks.

This module is intentionally safe to auto-import. It must never import the
Telegram runtime, start polling, replace routers, or create a second bot
Application. The Telegram lifecycle is owned exclusively by server.py.
"""
import logging

log = logging.getLogger("netyar.sitecustomize")

try:
    import bot as B
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

    def safe_kb(rows):
        return ReplyKeyboardMarkup(
            [[str(x) for x in (r or [])] for r in (rows or []) if r],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    # Keep keyboard construction deterministic without touching routing.
    B.kb = safe_kb

    async def safe_notify(app, message, request_id=None, inline=None, files=None):
        if not B.ADM:
            return
        ids = list(files or [])
        if request_id:
            try:
                ids += [
                    r["file_id"]
                    for r in B.db.conn.execute(
                        "SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",
                        (request_id,),
                    ).fetchall()
                    if r["file_id"]
                ]
            except Exception:
                log.exception("request files lookup failed")

        if request_id and inline is None:
            inline = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"req:v:{request_id}")],
                [
                    InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{request_id}"),
                    InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{request_id}"),
                ],
                [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{request_id}")],
                [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{request_id}")],
            ])

        for aid in B.ADM:
            try:
                await app.bot.send_message(chat_id=int(aid), text=message, reply_markup=inline)
                for fid in dict.fromkeys(ids):
                    try:
                        await app.bot.send_photo(
                            chat_id=int(aid),
                            photo=fid,
                            caption=f"📎 فایل درخواست #{request_id}",
                        )
                    except Exception:
                        try:
                            await app.bot.send_document(
                                chat_id=int(aid),
                                document=fid,
                                caption=f"📎 فایل درخواست #{request_id}",
                            )
                        except Exception:
                            log.exception("admin file forwarding failed")
            except Exception:
                log.exception("admin notification failed")

    B.notify_admins = safe_notify

    # Keep the useful request approval/rejection workflow, but do not wrap the
    # router or partner text handler. Those are now owned by bot.py directly.
    _old_admin = B.admin_cb

    async def safe_admin(update, context):
        q = update.callback_query
        data = (q.data or "").split(":")
        if not B.admin(q.from_user.id):
            return
        if len(data) >= 3 and data[0] == "req":
            try:
                rid = int(data[2])
            except ValueError:
                await q.answer("درخواست نامعتبر")
                return
            r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if not r:
                await q.answer("درخواست پیدا نشد")
                return
            await q.answer()

            if data[1] in {"a", "x"}:
                status = "approved" if data[1] == "a" else "rejected"
                B.db.conn.execute(
                    "UPDATE requests SET status=?,updated_at=? WHERE id=?",
                    (status, B.now(), rid),
                )
                B.db.conn.commit()
                u = B.db.conn.execute(
                    "SELECT platform,external_id FROM users WHERE id=?", (r["user_id"],)
                ).fetchone()
                if u and u["platform"] == "telegram":
                    try:
                        await context.bot.send_message(
                            chat_id=int(u["external_id"]),
                            text=(
                                "✅ خدمت شما توسط مدیریت تأیید شد."
                                if status == "approved"
                                else "❌ خدمت شما توسط مدیریت رد شد."
                            ),
                        )
                    except Exception:
                        log.exception("customer status notification failed")
                try:
                    await q.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                return await q.message.reply_text(
                    "✅ خدمت تأیید شد و نتیجه ارسال شد."
                    if status == "approved"
                    else "❌ خدمت رد شد و نتیجه ارسال شد.",
                    reply_markup=B.amenu(),
                )

            if data[1] == "p":
                pr = B.db.conn.execute(
                    "SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",
                    (rid,),
                ).fetchone()
                pid = str(pr["answer"]) if pr else ""
                if not pid:
                    p = B.db.conn.execute(
                        "SELECT id FROM partners WHERE id=?", (r["user_id"],)
                    ).fetchone()
                    pid = str(p["id"]) if p else ""
                if not pid:
                    return await q.message.reply_text("⚠️ این درخواست به همکار متصل نیست.", reply_markup=B.amenu())
                B.db.set_setting(f"partner_code_request_{pid}", f"{rid}|{B.now()}")
                chat = B.db.setting(f"partner_chat_{pid}", "")
                if not chat:
                    return await q.message.reply_text(
                        "⚠️ همکار هنوز یک‌بار وارد پنل نشده تا چت او ثبت شود.",
                        reply_markup=B.amenu(),
                    )
                try:
                    await context.bot.send_message(
                        chat_id=int(chat),
                        text=(
                            f"🔐 مدیریت برای درخواست {r['tracking_code']} کد تأیید همان خدمت را می‌خواهد.\n\n"
                            "فقط کد تأیید خدمت را بفرستید؛ رمز ورود پنل را ارسال نکنید."
                        ),
                        reply_markup=B.partner_kb(),
                    )
                    return await q.message.reply_text(
                        "✅ درخواست کد برای همکار ارسال شد.", reply_markup=B.amenu()
                    )
                except Exception:
                    log.exception("verification request failed")
                    return await q.message.reply_text(
                        "❌ ارسال درخواست کد به همکار انجام نشد.", reply_markup=B.amenu()
                    )

        return await _old_admin(update, context)

    B.admin_cb = safe_admin
    log.info("NetYar non-invasive Telegram compatibility hooks loaded")
except Exception:
    # sitecustomize must never prevent Python/Railway from starting.
    log.exception("NetYar compatibility hooks failed; continuing without hooks")
