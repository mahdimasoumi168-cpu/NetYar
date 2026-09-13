"""Final Telegram operations/reliability layer.

Owns the final request controls and the two-way admin/partner communication
channel. It deliberately stays above legacy routers and uses per-user state
plus request/partner mapping so conversations do not mix.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.final_ops_overlay")
MAX_ROUNDS = 10


def install(app, B):
    if getattr(B, "_final_ops_overlay_v2", False):
        return True

    def req_buttons(rid):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
            [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
            [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}"), InlineKeyboardButton("🔐 درخواست کد", callback_data=f"panel:askcode:{rid}")],
            [InlineKeyboardButton("🧩 درخواست کپچا", callback_data=f"req:captcha:{rid}"), InlineKeyboardButton("📝 درخواست نوشتار چکاپ", callback_data=f"req:checkup:{rid}")],
            [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
            [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")],
        ])

    def get_request(rid):
        try:
            return B.db.conn.execute("SELECT * FROM requests WHERE id=?", (int(rid),)).fetchone()
        except Exception:
            log.exception("request lookup failed")
            return None

    def get_partner_for_request(rid):
        r = get_request(rid)
        if not r:
            return None, None
        try:
            # New schema: requests.user_id may be the partner id.
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (r["user_id"],)).fetchone()
            if p:
                return r, p
        except Exception:
            pass
        try:
            mapped = str(B.db.setting(f"request_partner_{rid}", "") or "").strip()
            if mapped.isdigit():
                p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(mapped),)).fetchone()
                if p:
                    return r, p
        except Exception:
            pass
        # Legacy mapping: a request can point at a Telegram user row.
        try:
            u = B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram' LIMIT 1", (r["user_id"],)).fetchone()
            ext = str(u["external_id"] or "").strip() if u else ""
            if ext:
                partners = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
                for p in partners:
                    for key in (f"partner_chat_{p['id']}", f"partner_chat_{p['phone']}"):
                        if ext and ext == str(B.db.setting(key, "") or "").strip():
                            B.db.set_setting(f"request_partner_{rid}", str(p["id"]))
                            return r, p
        except Exception:
            log.exception("legacy partner mapping failed")
        return r, None

    def partner_chat(pid, phone=None):
        for key in (f"partner_chat_{pid}", f"partner_chat_{phone}" if phone else ""):
            if not key:
                continue
            value = str(B.db.setting(key, "") or "").strip()
            if value:
                try:
                    return int(value)
                except Exception:
                    pass
        return None

    def remember_chat(admin_id, partner_id, chat_id, rid=None):
        a = B.S.setdefault(int(admin_id), {})
        p = B.S.setdefault(int(chat_id), {})
        a["mode"] = "final_admin_chat"
        a["final_chat_partner"] = int(chat_id)
        a["final_chat_partner_id"] = int(partner_id)
        if rid:
            a["final_chat_rid"] = int(rid)
        p["mode"] = "final_partner_chat"
        p["partner_id"] = int(partner_id)
        p["final_chat_admin"] = int(admin_id)
        if rid:
            p["final_chat_rid"] = int(rid)
        try:
            B.db.set_setting(f"final_chat_admin_{partner_id}", str(admin_id))
            B.db.set_setting(f"final_chat_partner_{admin_id}", str(partner_id))
            if rid:
                B.db.set_setting(f"final_chat_request_{partner_id}", str(rid))
        except Exception:
            pass

    async def notify_admin(context, admin_id, text, rid=None, extra_markup=None):
        try:
            mk = extra_markup or (req_buttons(rid) if rid else None)
            await context.bot.send_message(chat_id=int(admin_id), text=text, reply_markup=mk)
            return True
        except Exception:
            log.exception("admin notification failed")
            return False

    async def admin_callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = str(q.data or "")
        if data.startswith("final:chat:"):
            try:
                pid = int(data.rsplit(":", 1)[1])
            except Exception:
                await q.answer("همکار نامعتبر است", show_alert=True)
                raise ApplicationHandlerStop
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            chat = partner_chat(pid, p["phone"] if p else None)
            if not p or not chat:
                await q.answer("همکار یا چت همکار پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop
            remember_chat(q.from_user.id, pid, chat)
            await q.answer("ارتباط فعال شد")
            await q.message.reply_text("💬 ارتباط با همکار فعال شد. پیام، عکس، فایل، صوت یا ویس را ارسال کنید.", reply_markup=B.amenu())
            await context.bot.send_message(chat_id=chat, text="💬 مدیریت ارتباط با شما را آغاز کرد. پیام، عکس، فایل، صوت یا ویس خود را ارسال کنید.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop

        if not (data.startswith("req:") or data.startswith("panel:askcode:")):
            return
        try:
            if data.startswith("panel:askcode:"):
                rid = int(data.rsplit(":", 1)[1]); action = "code"
            else:
                parts = data.split(":")
                if len(parts) < 3:
                    return
                rid = int(parts[2]); action = parts[1]
        except Exception:
            await q.answer("درخواست نامعتبر است", show_alert=True)
            raise ApplicationHandlerStop

        r, p = get_partner_for_request(rid)
        if not r:
            await q.answer("درخواست پیدا نشد", show_alert=True)
            raise ApplicationHandlerStop
        # These actions belong to the canonical request-control layer.
        if action in {"a", "x", "review", "payconfirm", "r"}:
            return
        if not p:
            await q.answer("همکار این درخواست مشخص نیست", show_alert=True)
            raise ApplicationHandlerStop
        chat = partner_chat(p["id"], p["phone"])
        if not chat:
            await q.answer("چت تلگرام همکار ثبت نشده است؛ همکار یک‌بار وارد پنل شود.", show_alert=True)
            raise ApplicationHandlerStop
        B.db.set_setting(f"request_partner_{rid}", str(p["id"]))

        if action in {"p", "code"}:
            key = f"final_code_round_{rid}"
            try: n = int(B.db.setting(key, "0") or 0)
            except Exception: n = 0
            if n >= MAX_ROUNDS:
                await q.answer("سقف ۱۰ درخواست کد تکمیل شده است", show_alert=True)
                raise ApplicationHandlerStop
            n += 1
            B.db.set_setting(key, str(n))
            B.db.set_setting(f"partner_code_request_{p['id']}", f"{rid}|{r['tracking_code']}")
            B.db.set_setting(f"partner_code_request_admin_{rid}", str(q.from_user.id))
            B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            st = B.S.setdefault(chat, {}); st.update(partner_id=p["id"], mode="partner_send_code", code_request_rid=rid, final_relay_admin=q.from_user.id)
            await context.bot.send_message(chat_id=chat, text=f"👔 مدیریت\n\n🔐 درخواست کد خدمت (نوبت {n} از {MAX_ROUNDS})\n🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n\nلطفاً کد را ارسال کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f"finalrelay:cancel:{rid}")]]))
            await q.answer(f"درخواست کد نوبت {n} از {MAX_ROUNDS} ارسال شد")
            raise ApplicationHandlerStop

        if action == "captcha":
            B.db.set_setting(f"final_relay_{q.from_user.id}", f"captcha|{rid}|{chat}")
            st = B.S.setdefault(q.from_user.id, {}); st["mode"] = "final_admin_captcha"; st["final_relay_rid"] = rid; st["final_relay_chat"] = chat
            await q.message.reply_text("🧩 درخواست کپچا\n\nلطفاً تصویر کپچا را همین‌جا ارسال کنید تا برای همکار مربوط به این درخواست فرستاده شود.")
            await q.answer("تصویر کپچا را ارسال کنید")
            raise ApplicationHandlerStop

        if action == "checkup":
            B.db.set_setting(f"final_relay_{q.from_user.id}", f"checkup|{rid}|{chat}")
            st = B.S.setdefault(q.from_user.id, {}); st["mode"] = "final_admin_checkup"; st["final_relay_rid"] = rid; st["final_relay_chat"] = chat
            await q.message.reply_text("📝 متن درخواست چکاپ را ارسال کنید تا برای همکار مربوطه فرستاده شود.")
            await q.answer("متن چکاپ را ارسال کنید")
            raise ApplicationHandlerStop

        if action == "chat":
            remember_chat(q.from_user.id, p["id"], chat, rid)
            await q.answer("ارتباط فعال شد")
            await q.message.reply_text("💬 ارتباط با همکار فعال شد. پیام، عکس، فایل، صوت یا ویس را ارسال کنید.", reply_markup=B.amenu())
            await context.bot.send_message(chat_id=chat, text=f"💬 مدیریت ارتباط با شما را آغاز کرد.\n🎫 درخواست: {r['tracking_code']}\nهر پیام، عکس، فایل، صوت یا ویس شما برای مدیریت ارسال می‌شود.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop

        if action == "bottom":
            await q.message.reply_text(f"📌 درخواست #{r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n\nدرخواست دوباره در انتهای چت قرار گرفت.", reply_markup=req_buttons(rid))
            try:
                rows = B.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id", (rid,)).fetchall()
                for row in rows:
                    fid = row["file_id"]
                    try:
                        await context.bot.send_photo(chat_id=q.from_user.id, photo=fid, caption=f"📎 فایل درخواست {r['tracking_code']}")
                    except Exception:
                        try: await context.bot.send_document(chat_id=q.from_user.id, document=fid, caption=f"📎 فایل درخواست {r['tracking_code']}")
                        except Exception: pass
            except Exception:
                log.exception("request attachment resend failed")
            await q.answer("درخواست به انتهای چت منتقل شد")
            raise ApplicationHandlerStop

        if action == "v":
            rows = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
            lines = [f"📋 اطلاعات کامل درخواست\n🎫 {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}"]
            for x in rows:
                if x["answer"]: lines.append(f"• {x['field_key']}: {x['answer']}")
                elif x["file_id"]: lines.append(f"• {x['field_key']}: 📎 فایل پیوست")
            await q.message.reply_text("\n".join(lines), reply_markup=req_buttons(rid))
            try:
                for x in rows:
                    if not x["file_id"]: continue
                    fid=x["file_id"]
                    try: await context.bot.send_photo(chat_id=q.from_user.id, photo=fid, caption=f"📎 {x['field_key']}")
                    except Exception:
                        try: await context.bot.send_document(chat_id=q.from_user.id, document=fid, caption=f"📎 {x['field_key']}")
                        except Exception: pass
            except Exception:
                log.exception("full request media delivery failed")
            await q.answer()
            raise ApplicationHandlerStop

    async def admin_media(update, context):
        uid = update.effective_user.id if update.effective_user else 0
        spec = str(B.db.setting(f"final_relay_{uid}", "") or "")
        msg = update.effective_message
        if not spec or not msg:
            return
        parts = spec.split("|", 2)
        if len(parts) != 3 or parts[0] != "captcha":
            return
        try: rid, chat = int(parts[1]), int(parts[2])
        except Exception: return
        fid = msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else None)
        if not fid: return
        try:
            await context.bot.send_photo(chat_id=chat, photo=fid, caption=f"🧩 تصویر کپچا برای درخواست {rid}\nلطفاً کد کپچا را ارسال کنید.")
        except Exception:
            await context.bot.send_document(chat_id=chat, document=fid, caption=f"🧩 تصویر کپچا برای درخواست {rid}\nلطفاً کد کپچا را ارسال کنید.")
        B.db.set_setting(f"final_relay_{uid}", f"captcha_wait|{rid}|{chat}")
        await msg.reply_text("✅ تصویر کپچا برای همکار ارسال شد. منتظر کد هستیم.")
        raise ApplicationHandlerStop

    async def text_router(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or not msg.text:
            return
        uid = user.id; st = B.S.setdefault(uid, {}); text = msg.text.strip()

        # Partner answers to code/captcha/checkup.
        if st.get("mode") in {"partner_send_code", "final_partner_code", "final_partner_captcha", "final_partner_checkup"}:
            rid = st.get("code_request_rid") or st.get("final_relay_rid")
            if rid and text:
                try:
                    req = get_request(rid); tracking = req["tracking_code"] if req else "-"
                    admin_id = st.get("final_relay_admin") or B.db.setting(f"partner_code_request_admin_{rid}", "") or B.db.setting(f"final_chat_admin_{st.get('partner_id')}", "")
                    if not admin_id: admin_id = next(iter(B.ADM), "")
                    mode = st.get("mode")
                    label = "🔐 کد خدمت" if mode in {"partner_send_code","final_partner_code"} else ("🧩 کد کپچا" if mode == "final_partner_captcha" else "📝 متن چکاپ")
                    delivered = await notify_admin(context, admin_id, f"📨 پاسخ همکار\n🎫 {tracking}\n{label}: {text}", rid)
                    if mode in {"partner_send_code","final_partner_code"}:
                        try:
                            B.db.answer(rid, "partner_code", answer=text)
                            B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
                        except Exception: log.exception("partner code save failed")
                    st["mode"] = None; st.pop("code_request_rid", None); st.pop("final_relay_rid", None)
                    return await msg.reply_text("✅ پاسخ برای مدیریت ارسال شد." if delivered else "⚠️ پاسخ دریافت شد ولی ارسال به مدیریت ناموفق بود.", reply_markup=B.partner_kb())
                except Exception:
                    log.exception("partner response routing failed")
                    return await msg.reply_text("❌ پردازش پاسخ انجام نشد؛ دوباره ارسال کنید.", reply_markup=B.partner_kb())

        # Admin sends checkup text after pressing its button.
        spec = str(B.db.setting(f"final_relay_{uid}", "") or "")
        if spec.startswith("checkup|"):
            _, rid, chat = spec.split("|", 2)
            await context.bot.send_message(chat_id=int(chat), text=f"📝 متن چکاپ درخواست {rid}:\n\n{text}")
            B.db.set_setting(f"final_relay_{uid}", "")
            st["mode"] = None
            return await msg.reply_text("✅ متن چکاپ برای همکار ارسال شد.", reply_markup=B.amenu())

        # Persistent two-way admin/partner text chat.
        if st.get("mode") == "final_admin_chat":
            chat = int(st.get("final_chat_partner"))
            await context.bot.send_message(chat_id=chat, text=f"👔 مدیریت:\n{text}")
            return
        if st.get("mode") == "final_partner_chat":
            admin = int(st.get("final_chat_admin"))
            await context.bot.send_message(chat_id=admin, text=f"👥 همکار:\n{text}")
            return

    async def media_router(update, context):
        user = update.effective_user
        msg = update.effective_message
        if not user or not msg: return
        st = B.S.setdefault(user.id, {})
        if st.get("mode") == "final_admin_chat":
            chat = int(st.get("final_chat_partner"))
            if msg.photo: await context.bot.send_photo(chat, msg.photo[-1].file_id, caption="👔 تصویر از مدیریت")
            elif msg.voice: await context.bot.send_voice(chat, msg.voice.file_id, caption="👔 ویس از مدیریت")
            elif msg.audio: await context.bot.send_audio(chat, msg.audio.file_id, caption="👔 صوت از مدیریت")
            elif msg.document: await context.bot.send_document(chat, msg.document.file_id, caption="👔 فایل از مدیریت")
            else: return
            raise ApplicationHandlerStop
        if st.get("mode") == "final_partner_chat":
            admin = int(st.get("final_chat_admin"))
            if msg.photo: await context.bot.send_photo(admin, msg.photo[-1].file_id, caption="👥 تصویر از همکار")
            elif msg.voice: await context.bot.send_voice(admin, msg.voice.file_id, caption="👥 ویس از همکار")
            elif msg.audio: await context.bot.send_audio(admin, msg.audio.file_id, caption="👥 صوت از همکار")
            elif msg.document: await context.bot.send_document(admin, msg.document.file_id, caption="👥 فایل از همکار")
            else: return
            raise ApplicationHandlerStop

    async def quick_buttons(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or not msg.text: return
        t = msg.text.strip(); uid = user.id; st = B.S.setdefault(uid, {})
        if t == "💬 ارتباط با مدیریت" and st.get("partner_id"):
            pid = st.get("partner_id"); chat = partner_chat(pid, st.get("phone"))
            admin_id = B.db.setting(f"final_chat_admin_{pid}", "") or next(iter(B.ADM), "")
            if not chat or not admin_id: return await msg.reply_text("❌ اتصال ارتباط با مدیریت کامل نیست.", reply_markup=B.partner_kb())
            remember_chat(int(admin_id), int(pid), int(chat))
            await context.bot.send_message(chat_id=int(admin_id), text=f"💬 همکار درخواست ارتباط با مدیریت دارد.\n👤 شناسه همکار: {pid}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 باز کردن گفتگو", callback_data=f"final:chat:{pid}")]]))
            return await msg.reply_text("💬 ارتباط با مدیریت فعال شد. پیام، عکس، فایل، صوت یا ویس خود را ارسال کنید.", reply_markup=B.partner_kb())
        if t == "💬 ارتباط با همکار" and B.admin(uid):
            return await msg.reply_text("💬 برای شروع گفتگو، از داخل درخواست روی «ارتباط با همکار» بزنید یا اعلان درخواست ارتباط همکار را باز کنید.", reply_markup=B.amenu())

    old_pkb = B.partner_kb
    def partner_kb(*args, **kwargs):
        base = old_pkb(*args, **kwargs)
        rows = [list(r) for r in getattr(base, "keyboard", [])]
        if not any("ارتباط با مدیریت" in str(x) for row in rows for x in row):
            rows.insert(max(0, len(rows)-1), ["💬 ارتباط با مدیریت"])
        return type(base)(rows, resize_keyboard=True)
    B.partner_kb = partner_kb

    old_amenu = B.amenu
    def amenu(*args, **kwargs):
        base = old_amenu(*args, **kwargs)
        rows = [list(r) for r in getattr(base, "keyboard", [])]
        if not any("ارتباط با همکار" in str(x) for row in rows for x in row):
            rows.insert(max(0, len(rows)-1), ["💬 ارتباط با همکار"])
        return type(base)(rows, resize_keyboard=True)
    B.amenu = amenu

    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^(req:|panel:askcode:|final:chat:)"), group=-40000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quick_buttons), group=-39999)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, admin_media), group=-39998)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router), group=-39997)
    app.add_handler(MessageHandler(filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL, media_router), group=-39996)
    B._final_ops_overlay_v2 = True
    return True
