"""Complete request/admin workflow layer.
Adds reliable request controls, file forwarding, partner-code requests and safer partner chat binding.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
log = logging.getLogger("netyar.workflow")


def install():
    import bot as B
    if getattr(B, "_netyar_workflow_installed", False):
        return

    original_notify = B.notify_admins
    original_admin_cb = B.admin_cb
    original_partner = B.partner
    original_router = B.router

    def bind_request_partner(request_id):
        """Resolve the partner owning a request, including legacy requests whose user_id stores partner.id."""
        try:
            r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
            if not r:
                return None
            # Explicit binding wins.
            pid = B.db.setting(f"request_partner_{request_id}", "")
            if pid:
                p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (int(pid),)).fetchone()
                if p:
                    return p
            # Current schema uses users.id, but older partner-originated requests may have stored partner.id.
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (r["user_id"],)).fetchone()
            if p:
                B.db.set_setting(f"request_partner_{request_id}", str(p["id"]))
                return p
            return None
        except Exception:
            log.exception("request partner resolution failed")
            return None

    async def notify_admins(app, message, request_id=None, inline=None):
        if not request_id:
            return await original_notify(app, message, request_id, inline)
        p = bind_request_partner(request_id)
        if p:
            B.db.set_setting(f"request_partner_{request_id}", str(p["id"]))
        controls = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات", callback_data=f"req:v:{request_id}")],
            [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{request_id}"),
             InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{request_id}")],
            [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:c:{request_id}"),
             InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{request_id}")],
        ])
        await original_notify(app, message, request_id=None, inline=controls)
        if not B.ADM:
            return
        rows = B.db.conn.execute(
            "SELECT field_key,file_id FROM request_answers WHERE request_id=? AND file_id<>'' ORDER BY id",
            (request_id,),
        ).fetchall()
        for aid in B.ADM:
            for row in rows:
                try:
                    await app.bot.send_document(
                        chat_id=int(aid), document=row["file_id"],
                        caption=f"📎 فایل درخواست #{request_id} — {row['field_key']}"
                    )
                except Exception:
                    try:
                        await app.bot.send_photo(
                            chat_id=int(aid), photo=row["file_id"],
                            caption=f"📎 تصویر درخواست #{request_id} — {row['field_key']}"
                        )
                    except Exception:
                        log.exception("request file forwarding failed")

    async def partner(u, c):
        result = await original_partner(u, c)
        try:
            uid = u.effective_user.id
            st = B.S.setdefault(uid, {})
            pid = st.get("partner_id")
            if pid:
                B.db.set_setting(f"partner_chat_{pid}", str(uid))
        except Exception:
            log.exception("partner chat binding failed")
        return result

    async def admin_cb(u, c):
        q = u.callback_query
        data = (q.data or "").split(":")
        if len(data) >= 3 and data[0] == "req" and B.admin(q.from_user.id):
            try:
                rid = int(data[2])
                r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                if not r:
                    await q.answer("درخواست پیدا نشد", show_alert=True)
                    return
                action = data[1]
                if action in {"a", "x"}:
                    status = "approved" if action == "a" else "rejected"
                    B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (status, B.now(), rid))
                    B.db.audit("telegram", q.from_user.id, f"request_{status}", rid, r["tracking_code"])
                    B.db.conn.commit()
                    user = B.db.conn.execute("SELECT external_id,platform FROM users WHERE id=?", (r["user_id"],)).fetchone()
                    if user and user["platform"] == "telegram":
                        try:
                            txt = "✅ خدمت شما تأیید شد." if status == "approved" else "❌ درخواست خدمت شما رد شد."
                            await q.bot.send_message(chat_id=int(user["external_id"]), text=f"{txt}\n🎫 کد پیگیری: {r['tracking_code']}")
                        except Exception:
                            log.exception("user status notification failed")
                    await q.answer("انجام شد")
                    return await q.message.reply_text(
                        f"{'✅ خدمت تأیید شد' if status == 'approved' else '❌ خدمت رد شد'}\n🎫 {r['tracking_code']}",
                        reply_markup=B.amenu(),
                    )
                if action == "c":
                    p = bind_request_partner(rid)
                    if not p:
                        await q.answer("همکار این درخواست مشخص نیست", show_alert=True)
                        return
                    chat = B.db.setting(f"partner_chat_{p['id']}", "")
                    if not chat:
                        await q.answer("همکار هنوز وارد پنل نشده است", show_alert=True)
                        return
                    B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", ("awaiting_partner_code", B.now(), rid))
                    B.db.audit("telegram", q.from_user.id, "request_partner_code", rid, r["tracking_code"])
                    B.db.conn.commit()
                    B.S.setdefault(int(chat), {}).update({
                        "mode": "partner_code_reply",
                        "partner_id": p["id"],
                        "partner_code_rid": rid,
                    })
                    await q.bot.send_message(
                        chat_id=int(chat),
                        text=(f"🔐 مدیریت برای درخواست شما اطلاعات تکمیلی می‌خواهد.\n\n"
                              f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n\n"
                              "لطفاً کد/رمز یا اطلاعات موردنیاز را همین‌جا ارسال کنید."),
                        reply_markup=B.kb([[B.CANCEL]])
                    )
                    await q.answer("درخواست کد برای همکار ارسال شد")
                    return await q.message.reply_text("🔐 درخواست کد/اطلاعات برای همکار ارسال شد.", reply_markup=B.amenu())
            except Exception:
                log.exception("request workflow callback failed")
                await q.answer("خطا در پردازش درخواست", show_alert=True)
                return
        return await original_admin_cb(u, c)

    async def router(u, c):
        try:
            uid = u.effective_user.id
            st = B.S.setdefault(uid, {})
            text = (u.message.text or "").strip() if getattr(u, "message", None) else ""
            rid = int(st.get("partner_code_rid", 0) or 0)
            # Handle partner reply before every other text handler. This prevents
            # partner-panel/menu routers from swallowing the requested code.
            if st.get("mode") == "partner_code_reply" and rid:
                if text in {B.CANCEL, "❌ Cancel", "❌ إلغاء"}:
                    st["mode"] = None
                    st.pop("partner_code_rid", None)
                    return await u.message.reply_text("❌ عملیات لغو شد.", reply_markup=B.partner_kb())
                r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                if not r:
                    st["mode"] = None
                    st.pop("partner_code_rid", None)
                    return await u.message.reply_text("❌ درخواست پیدا نشد.", reply_markup=B.partner_kb())
                B.db.answer(rid, "partner_code", answer=text)
                B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", ("awaiting_review", B.now(), rid))
                B.db.conn.commit()
                st["mode"] = None
                st.pop("partner_code_rid", None)
                await B.notify_admins(
                    c.application,
                    f"🔐 اطلاعات تکمیلی همکار دریافت شد\n🎫 {r['tracking_code']}\n🧾 {r['service_key']}\n\n{text}",
                    rid,
                )
                return await u.message.reply_text("✅ اطلاعات دریافت شد و برای مدیریت ارسال شد.", reply_markup=B.partner_kb())
        except Exception:
            log.exception("partner code router failed")
        return await original_router(u, c)

    B.notify_admins = notify_admins
    B.admin_cb = admin_cb
    B.partner = partner
    B.router = router
    B._netyar_workflow_installed = True
    log.info("NetYar complete workflow patch installed")