"""Reliable Telegram partner-code requests.

Keeps partner chat IDs stable by resolving them from both partner-id and
phone settings, and resolves legacy requests whose requests.user_id points
to a Telegram user row instead of the partner row.
"""
import asyncio
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram_partner_code_reliable")
MAX_CODE_REQUESTS = 10


def install(app, B):
    if getattr(B, "_partner_code_reliable_installed", False):
        return

    async def resolve_partner(r):
        """Resolve the partner assigned to a request across old/new schemas."""
        rid = int(r["id"])
        try:
            p = B.db.conn.execute(
                "SELECT id,phone,name,active FROM partners WHERE id=?",
                (r["user_id"],),
            ).fetchone()
            if p and int(p["active"] or 0) == 1:
                return p
        except Exception:
            pass

        external_id = ""
        try:
            u = B.db.conn.execute(
                "SELECT external_id FROM users WHERE id=? AND platform='telegram'",
                (r["user_id"],),
            ).fetchone()
            if u:
                external_id = str(u["external_id"] or "").strip()
        except Exception:
            pass

        if external_id:
            try:
                partners = B.db.conn.execute(
                    "SELECT id,phone,name,active FROM partners WHERE active=1 ORDER BY id DESC"
                ).fetchall()
                for p in partners:
                    pid = str(p["id"])
                    phone = str(p["phone"] or "")
                    by_id = B.db.setting(f"partner_chat_{pid}", "")
                    by_phone = B.db.setting(f"partner_chat_{phone}", "")
                    if external_id in {str(by_id).strip(), str(by_phone).strip()}:
                        B.db.set_setting(f"request_partner_{rid}", str(p["id"]))
                        return p
            except Exception:
                log.exception("legacy partner mapping lookup failed")

        try:
            mapped = B.db.setting(f"request_partner_{rid}", "").strip()
            if mapped.isdigit():
                p = B.db.conn.execute(
                    "SELECT id,phone,name,active FROM partners WHERE id=? AND active=1",
                    (int(mapped),),
                ).fetchone()
                if p:
                    return p
        except Exception:
            pass
        return None

    async def resolve_partner_chat(pid, phone=None):
        candidates = []
        for key in (f"partner_chat_{pid}", f"partner_chat_{phone}" if phone else ""):
            if key:
                value = B.db.setting(key, "")
                if value:
                    candidates.append(value)
        for value in candidates:
            try:
                return int(value)
            except Exception:
                continue
        return None

    async def ask_code(update, context):
        q = update.callback_query
        data = str(q.data or "")
        if not data.startswith("panel:askcode:"):
            return
        if not B.admin(q.from_user.id):
            await q.answer("دسترسی ندارید", show_alert=True)
            raise ApplicationHandlerStop
        try:
            rid = int(data.rsplit(":", 1)[1])
            r = B.db.conn.execute(
                "SELECT id,user_id,tracking_code,service_key FROM requests WHERE id=?",
                (rid,),
            ).fetchone()
            if not r:
                await q.answer("درخواست پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop

            p = await resolve_partner(r)
            if not p:
                await q.answer("همکار فعال برای این درخواست پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop

            attempt_key = f"partner_code_attempts_{rid}"
            attempts = int(B.db.setting(attempt_key, "0") or 0)
            if attempts >= MAX_CODE_REQUESTS:
                await q.answer(f"حداکثر {MAX_CODE_REQUESTS} درخواست کد مجاز است.", show_alert=True)
                await q.message.reply_text(
                    f"⚠️ سقف {MAX_CODE_REQUESTS} درخواست کد برای این درخواست استفاده شده است."
                )
                raise ApplicationHandlerStop

            chat_id = await resolve_partner_chat(p["id"], p["phone"])
            if not chat_id:
                await q.answer("چت تلگرام همکار ثبت نشده است؛ همکار یک‌بار وارد پنل شود.", show_alert=True)
                raise ApplicationHandlerStop

            attempts += 1
            B.db.set_setting(attempt_key, str(attempts))
            B.db.set_setting(f"partner_code_request_{p['id']}", f"{rid}|{r['tracking_code']}")
            B.db.set_setting(f"partner_code_request_admin_{rid}", str(q.from_user.id))
            B.db.set_setting(f"partner_chat_{p['id']}", str(chat_id))
            B.db.set_setting(f"partner_chat_{p['phone']}", str(chat_id))
            B.db.set_setting(f"request_partner_{rid}", str(p["id"]))
            B.db.conn.execute(
                "UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()

            state = B.S.setdefault(chat_id, {})
            state.update(partner_id=p["id"], mode="partner_send_code", code_request_rid=rid)
            message = (
                "👔 مدیریت\n\n"
                f"📨 درخواست کد خدمت (نوبت {attempts} از {MAX_CODE_REQUESTS})\n"
                f"🎫 کد پیگیری: {r['tracking_code']}\n"
                f"🧾 خدمت: {r['service_key']}\n\n"
                "لطفاً کد خدمت/کد انجام کار را همین‌جا ارسال کنید."
            )
            last_error = None
            for attempt in range(3):
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f"pc:x:{rid}:{p['id']}")]]),
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        await asyncio.sleep(0.7 * (attempt + 1))
            if last_error:
                log.exception("partner code request delivery failed")
                await q.answer("ارسال به همکار انجام نشد؛ دوباره تلاش کنید.", show_alert=True)
                raise ApplicationHandlerStop

            await q.answer(f"درخواست کد نوبت {attempts} از {MAX_CODE_REQUESTS} ارسال شد")
            await q.message.reply_text(
                f"✅ درخواست کد نوبت {attempts} از {MAX_CODE_REQUESTS} برای «{p['name'] or p['phone']}» ارسال شد.\n🎫 {r['tracking_code']}"
            )
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("reliable partner code request failed")
            await q.answer("خطا در ارسال درخواست کد", show_alert=True)
            raise ApplicationHandlerStop

    async def code_reply(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        rid = st.get("code_request_rid")
        if st.get("mode") != "partner_send_code" or not pid or not rid:
            return
        text = (update.message.text or "").strip()
        if not text:
            await update.message.reply_text("❌ کد خالی است؛ کد خدمت را ارسال کنید.")
            raise ApplicationHandlerStop
        req = B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?", (rid,)).fetchone()
        p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
        tracking = req["tracking_code"] if req else "-"
        B.db.answer(rid, "partner_code", answer=text)
        B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.commit()
        admin_text = (
            "👔 مدیر — کد از همکار دریافت شد\n\n"
            f"👤 همکار: {p['name'] if p else '-'}\n"
            f"📱 شماره: {p['phone'] if p else '-'}\n"
            f"🆔 شناسه تلگرام: {uid}\n"
            f"🎫 کد پیگیری: {tracking}\n"
            f"🔐 کد خدمت: {text}"
        )
        delivered = False
        admin_id = B.db.setting(f"partner_code_request_admin_{rid}", "").strip()
        recipients = [admin_id] if admin_id else [str(aid) for aid in B.ADM]
        for aid in recipients:
            if not aid:
                continue
            for attempt in range(3):
                try:
                    await context.bot.send_message(chat_id=int(aid), text=admin_text)
                    delivered = True
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(0.7 * (attempt + 1))
                    else:
                        log.exception("partner code admin notification failed")
        B.db.set_setting(f"partner_code_request_{pid}", "")
        B.db.set_setting(f"partner_code_request_admin_{rid}", "")
        st["mode"] = None
        st.pop("code_request_rid", None)
        await update.message.reply_text(
            "✅ کد خدمت دریافت شد و برای مدیریت ارسال شد." if delivered else "⚠️ کد دریافت شد، اما ارسال اعلان مدیریت ناموفق بود؛ مدیریت می‌تواند درخواست را دوباره پیگیری کند.",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(ask_code, pattern=r"^panel:askcode:"), group=-110)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, code_reply), group=-89)
    B._partner_code_reliable_installed = True
