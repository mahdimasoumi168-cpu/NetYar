import asyncio
import logging
from telegram import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("netyar.enhancements")


def _button_style(text):
    text = str(text)
    if any(x in text for x in ("تأیید", "فعال", "شارژ", "ذخیره", "Approve", "Active")):
        return "success"
    if any(x in text for x in ("انصراف", "رد", "حذف", "لغو", "Reject", "Delete", "Cancel")):
        return "danger"
    return "primary"


def _kb(rows):
    out = []
    for row in rows or []:
        rr = []
        for text in row or []:
            try:
                rr.append(KeyboardButton(text=str(text), style=_button_style(text)))
            except Exception:
                rr.append(KeyboardButton(text=str(text)))
        if rr:
            out.append(rr)
    return ReplyKeyboardMarkup(out, resize_keyboard=True)


def _inline(rows):
    out = []
    for row in rows or []:
        rr = []
        for text, data in row or []:
            try:
                rr.append(InlineKeyboardButton(str(text), callback_data=str(data), style=_button_style(text)))
            except Exception:
                rr.append(InlineKeyboardButton(str(text), callback_data=str(data)))
        if rr:
            out.append(rr)
    return InlineKeyboardMarkup(out)


def install():
    try:
        import bot
        from core import db, now

        original_notify = bot.notify_admins
        original_admin_cb = bot.admin_cb
        original_admin_text = bot.admin_text
        original_partner = bot.partner
        original_ptext = bot.ptext
        original_service_text = bot.service_text

        bot.kb = _kb

        def menu_text():
            return (
                "📋 خدمات قابل استفاده:\n\n"
                "1️⃣ 🪪 فیدای غیر حضوری\n"
                "2️⃣ 🖨 خدمات چاپ\n"
                "3️⃣ 🏛 حل مشکل ورود اتباع دولت من\n"
                "4️⃣ 🎫 کد رهگیری تمدید کارت‌ها\n"
                "5️⃣ 📱 خدمات سیم‌کارت\n"
                "6️⃣ 📝 آزمون غربالگری\n"
                "7️⃣ 🎫 پیگیری\n"
                "8️⃣ 💰 کیف پول من\n"
                "9️⃣ 📞 تماس با ما\n"
                "🔟 📝 ثبت شکایت مشتریان\n"
                "👥 پنل همکاران\n\n"
                "لطفاً یکی از گزینه‌های بالا را انتخاب کنید."
            )

        async def start(u, c):
            uid = u.effective_user.id
            bot.db.user("telegram", uid, u.effective_user.username, u.effective_user.full_name)
            bot.S[uid] = {}
            await u.message.reply_text(
                "سلام و خوش آمدید 🌷\n\n"
                "گزینه‌های زبان:\n"
                "1️⃣ 🇮🇷 فارسی\n2️⃣ 🇬🇧 English\n3️⃣ 🇸🇦 العربية\n\n"
                "لطفاً یکی را انتخاب کنید:",
                reply_markup=_inline([[('🇮🇷 فارسی', 'lang:fa'), ('🇬🇧 English', 'lang:en')], [('🇸🇦 العربية', 'lang:ar')]])
            )
        bot.start = start

        async def statuscb(u, c):
            q = u.callback_query
            await q.answer()
            uid = q.from_user.id
            bot.S.setdefault(uid, {})["status"] = q.data.split(":", 1)[1]
            if bot.S[uid]["status"] == "foreign":
                await q.message.reply_text(menu_text(), reply_markup=bot.main(uid))
            else:
                await q.message.reply_text("🇮🇷 خدمات کاربران ایرانی در حال حاضر فعال نیست.", reply_markup=bot.main(uid))
        bot.statuscb = statuscb

        async def notify(app, message, request_id=None, inline=None, files=None):
            if not bot.ADM:
                return
            file_ids = list(files or [])
            tracking = ""
            partner_id = ""
            if request_id:
                try:
                    req = db.conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
                    if req:
                        tracking = req["tracking_code"]
                        p = db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1", (req["user_id"],)).fetchone()
                        if p:
                            partner_id = str(p["id"])
                            exists = db.conn.execute(
                                "SELECT 1 FROM request_answers WHERE request_id=? AND field_key='partner_id' LIMIT 1",
                                (request_id,)
                            ).fetchone()
                            if not exists:
                                db.answer(request_id, "partner_id", answer=partner_id)
                                db.conn.commit()
                    rows = db.conn.execute(
                        "SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",
                        (request_id,)
                    ).fetchall()
                    file_ids.extend(r["file_id"] for r in rows)
                except Exception:
                    log.exception("request enrichment failed")

            if request_id and inline is None:
                inline = _inline([
                    [("🔎 مشاهده درخواست", f"req:v:{request_id}")],
                    [("✅ تأیید خدمت", f"req:a:{request_id}"), ("❌ رد خدمت", f"req:x:{request_id}")],
                    [("🔐 درخواست کد از همکار", f"req:p:{request_id}")],
                    [("✉️ پاسخ", f"req:r:{request_id}")],
                ])

            for aid in bot.ADM:
                try:
                    await app.bot.send_message(chat_id=int(aid), text=message, reply_markup=inline)
                    for fid in dict.fromkeys(x for x in file_ids if x):
                        try:
                            await app.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"📎 فایل درخواست {tracking or request_id}")
                        except Exception:
                            await app.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 فایل درخواست {tracking or request_id}")
                except Exception:
                    log.exception("admin notification failed")

        bot.notify_admins = notify

        async def partner(u, c):
            st = bot.S.setdefault(u.effective_user.id, {})
            if st.get("partner_id"):
                db.set_setting(f"partner_chat_{st['partner_id']}", str(u.effective_user.id))
            return await original_partner(u, c)
        bot.partner = partner

        async def ptext(u, c):
            uid = u.effective_user.id
            st = bot.S.setdefault(uid, {})
            text = (u.message.text or "").strip()
            pid = st.get("partner_id")
            pending = db.setting(f"partner_code_request_{pid}", "") if pid else ""
            if pid and pending and text and text not in {bot.CANCEL, "❌ لغو", "لغو"}:
                rid = int(pending)
                req = db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                if req:
                    db.answer(rid, "verification_code", answer=text)
                    db.set_setting(f"partner_code_request_{pid}", "")
                    db.conn.commit()
                    for aid in bot.ADM:
                        try:
                            await c.bot.send_message(
                                chat_id=int(aid),
                                text=f"🔐 کد تأیید همکار دریافت شد.\n🎫 {req['tracking_code']}\n👥 همکار: {pid}\n🔑 کد: {text}",
                                reply_markup=_inline([
                                    [("🔎 مشاهده درخواست", f"req:v:{rid}")],
                                    [("✅ تأیید خدمت", f"req:a:{rid}"), ("❌ رد خدمت", f"req:x:{rid}")],
                                ])
                            )
                        except Exception:
                            log.exception("verification code admin notification failed")
                    return await u.message.reply_text("✅ کد تأیید دریافت شد و برای مدیریت ارسال شد.", reply_markup=bot.partner_kb())
            return await original_ptext(u, c)
        bot.ptext = ptext

        async def service_text(u, c):
            st = bot.S.setdefault(u.effective_user.id, {})
            if st.get("mode") == "fida_phone":
                p = bot.normalize_phone(u.message.text)
                if not p:
                    return await u.message.reply_text(
                        "❌ شماره موبایل معتبر نیست.\nمثال صحیح: 09123456789",
                        reply_markup=bot.cancel_kb()
                    )
                uid = u.effective_user.id
                partner_id = st.get("partner_id")
                owner = partner_id or db.user("telegram", uid, u.effective_user.username, u.effective_user.full_name)
                rid, code = db.create_request(owner, "fida", "telegram", int(db.setting("price_fida", "0") or 0))
                if partner_id:
                    db.answer(rid, "partner_id", answer=str(partner_id))
                db.answer(rid, "document", file_id=st.get("doc", ""))
                db.answer(rid, "phone", answer=p)
                db.conn.execute("UPDATE requests SET status='submitted', payment_status='paid', updated_at=? WHERE id=?", (now(), rid))
                db.conn.commit()
                st["mode"] = None
                asyncio.create_task(bot.notify_admins(
                    c.application,
                    f"🆕 درخواست فیدای غیرحضوری\n🎫 کد پیگیری: {code}\n📱 شماره: {p}\n🪪 مدرک: پیوست شده",
                    rid
                ))
                return await u.message.reply_text(
                    f"✅ درخواست فیدای غیرحضوری با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n\nمدیریت پس از بررسی نتیجه را اعلام می‌کند.",
                    reply_markup=bot.partner_kb() if partner_id else bot.main(uid)
                )
            return await original_service_text(u, c)
        bot.service_text = service_text

        def full_amenu():
            return _kb([
                ["👤 پنل کاربران", "👥 همکاران"],
                ["💰 شارژها", "💰 پرداخت‌های مشتری"],
                ["📋 درخواست‌ها", "⚙️ قیمت‌ها"],
                ["🤖 مدیریت پیام‌رسان‌ها", "🌐 زبان‌ها"],
                ["📊 گزارش", "⚙️ تنظیمات"],
                ["🩺 سلامت ربات‌ها"],
                ["⬅️ منوی اصلی"],
            ])
        bot.amenu = full_amenu

        async def admin_text(u, c):
            if not bot.admin(u.effective_user.id):
                return
            t = (u.message.text or "").strip()
            if t == "🌐 زبان‌ها":
                current = db.setting("default_lang", "fa")
                return await u.message.reply_text(
                    f"🌐 مدیریت زبان‌ها\n\n🇮🇷 فارسی: فعال\n🇬🇧 English: فعال\n🇸🇦 العربية: فعال\n\nزبان پیش‌فرض فعلی: {current}",
                    reply_markup=_inline([
                        [("🇮🇷 فارسی", "langset:fa"), ("🇬🇧 English", "langset:en")],
                        [("🇸🇦 العربية", "langset:ar")],
                    ])
                )
            if t == "🤖 مدیریت پیام‌رسان‌ها":
                rows = db.bots()
                text = "🤖 مدیریت پیام‌رسان‌ها\n\n"
                if rows:
                    text += "\n".join(
                        f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'🟢 فعال' if r['active'] else '🔴 غیرفعال'} | {r['status']}"
                        for r in rows
                    )
                else:
                    text += "هنوز باتی ثبت نشده است."
                text += "\n\n⚠️ برای فعال‌سازی واقعی پیام‌رسان جدید باید آداپتور همان پیام‌رسان در runtime نصب باشد؛ ثبت صرف API به‌تنهایی بات را اجرا نمی‌کند."
                return await u.message.reply_text(text, reply_markup=full_amenu())
            if t == "🩺 سلامت ربات‌ها":
                return await u.message.reply_text(
                    "🩺 سلامت ربات‌ها\n\n🟢 Telegram: فعال و در حال پاسخ\n🟢 Rubika: فعال و webhook دریافت می‌کند\n\nاگر سرویس جدید اضافه شود، قبل از فعال‌سازی باید آداپتور و endpoint آن بررسی شود تا Telegram/Rubika قطع نشوند.",
                    reply_markup=full_amenu()
                )
            if t == "⚙️ تنظیمات":
                return await u.message.reply_text(
                    "⚙️ تنظیمات\n\n"
                    f"وضعیت بات: {'🟢 باز' if db.setting('bot_open','1') == '1' else '🔴 بسته'}\n"
                    "قیمت‌ها از بخش «⚙️ قیمت‌ها» مدیریت می‌شوند.\n"
                    "زبان پیش‌فرض از بخش «🌐 زبان‌ها» تغییر می‌کند.",
                    reply_markup=full_amenu()
                )
            return await original_admin_text(u, c)
        bot.admin_text = admin_text

        async def admin_cb(u, c):
            q = u.callback_query
            data = (q.data or "").split(":")
            if data and data[0] == "langset" and bot.admin(q.from_user.id):
                lang = data[1] if len(data) > 1 and data[1] in {"fa", "en", "ar"} else "fa"
                db.set_setting("default_lang", lang)
                await q.answer("ذخیره شد")
                return await q.message.reply_text(f"✅ زبان پیش‌فرض روی {lang} تنظیم شد.", reply_markup=bot.amenu())

            if data and data[0] == "req" and len(data) >= 3 and bot.admin(q.from_user.id):
                rid = int(data[2])
                r = db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                if not r:
                    await q.answer("درخواست پیدا نشد")
                    return
                if data[1] == "v":
                    await q.answer()
                    ans = db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
                    details = "\n".join(f"• {x['field_key']}: {x['answer']}" + (" 📎" if x['file_id'] else "") for x in ans) or "• اطلاعات تکمیلی ثبت نشده است."
                    return await q.message.reply_text(
                        f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n💰 مبلغ: {r['amount']:,} تومان\n💳 پرداخت: {r['payment_status']}\n\n{details}",
                        reply_markup=_inline([
                            [("✅ تأیید خدمت", f"req:a:{rid}"), ("❌ رد خدمت", f"req:x:{rid}")],
                            [("🔐 درخواست کد از همکار", f"req:p:{rid}")],
                            [("✉️ پاسخ", f"req:r:{rid}")],
                        ])
                    )
                if data[1] in {"a", "x"}:
                    await q.answer()
                    status = "approved" if data[1] == "a" else "rejected"
                    db.conn.execute("UPDATE requests SET status=?, updated_at=? WHERE id=?", (status, now(), rid))
                    db.conn.commit()
                    pid_row = db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1", (rid,)).fetchone()
                    pid = str(pid_row["answer"]) if pid_row else ""
                    if not pid:
                        p = db.conn.execute("SELECT id FROM partners WHERE id=?", (r["user_id"],)).fetchone()
                        pid = str(p["id"]) if p else ""
                    sent = False
                    if pid:
                        chat = db.setting(f"partner_chat_{pid}", "")
                        if chat:
                            try:
                                await c.bot.send_message(chat_id=int(chat), text=("✅ خدمت شما توسط مدیریت تأیید شد." if status == "approved" else "❌ درخواست شما توسط مدیریت رد شد."), reply_markup=bot.partner_kb())
                                sent = True
                            except Exception:
                                log.exception("partner status notification failed")
                    if not sent:
                        user = db.conn.execute("SELECT platform,external_id FROM users WHERE id=?", (r["user_id"],)).fetchone()
                        if user and user["platform"] == "telegram":
                            try:
                                await c.bot.send_message(chat_id=int(user["external_id"]), text=("✅ خدمت شما تأیید شد." if status == "approved" else "❌ درخواست شما رد شد."))
                            except Exception:
                                pass
                    await q.message.edit_reply_markup(reply_markup=None)
                    return await q.message.reply_text("✅ خدمت تأیید شد و نتیجه برای درخواست‌کننده ارسال شد." if status == "approved" else "❌ خدمت رد شد و نتیجه برای درخواست‌کننده ارسال شد.", reply_markup=bot.amenu())
                if data[1] == "p":
                    await q.answer()
                    ans = db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1", (rid,)).fetchone()
                    pid = str(ans["answer"]) if ans else ""
                    if not pid:
                        p = db.conn.execute("SELECT id FROM partners WHERE id=?", (r["user_id"],)).fetchone()
                        pid = str(p["id"]) if p else ""
                    if not pid:
                        return await q.message.reply_text("⚠️ این درخواست به همکار متصل نیست.", reply_markup=bot.amenu())
                    db.set_setting(f"partner_code_request_{pid}", str(rid))
                    chat = db.setting(f"partner_chat_{pid}", "")
                    if chat:
                        try:
                            await c.bot.send_message(chat_id=int(chat), text=f"🔐 مدیریت برای درخواست {r['tracking_code']} کد تأیید می‌خواهد.\n\nلطفاً فقط کد تأیید همان خدمت را ارسال کنید.\nرمز ورود پنل یا رمز حساب خود را ارسال نکنید.", reply_markup=bot.partner_kb())
                            return await q.message.reply_text("✅ درخواست کد برای همکار ارسال شد.", reply_markup=bot.amenu())
                        except Exception:
                            log.exception("partner code request failed")
                    return await q.message.reply_text("⚠️ چت همکار پیدا نشد. همکار یک‌بار وارد پنل همکاران شود تا اتصال چت ثبت شود.", reply_markup=bot.amenu())
            return await original_admin_cb(u, c)
        bot.admin_cb = admin_cb
        log.info("NetYar Telegram safe enhancements installed")
    except Exception:
        log.exception("Telegram enhancement failed; original bot remains active")

    try:
        import rubika_v2 as rb
        original_handle = rb.handle
        if not getattr(rb, "_netyar_wording_fixed", False):
            def handle(uid, chat, x, u):
                st = rb.STATE.setdefault(str(uid), {})
                if st.get("step") == "partner" and (str(x).startswith("5") or "دولت من" in str(x)):
                    st["step"] = "partner_gov_fida"
                    rb.send(chat, "🏛 حل مشکل سامانه دولت من\n\n🆔 شناسه فیدا یا شناسه اختصاصی مشترک را وارد کنید:", [[("0", rb.CANCEL)]])
                    return
                return original_handle(uid, chat, x, u)
            rb.handle = handle
            rb._netyar_wording_fixed = True
    except Exception:
        log.exception("Rubika wording enhancement failed")
