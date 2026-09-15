"""Reliable Telegram security-code flow plus final Telegram safety guards.

Security-code routing is request-scoped: manager -> exact partner -> exact
requesting manager. This module also installs the authoritative early guards
for Persian-only startup and the 07:00-19:00 Tehran public-hours gate.
"""
import asyncio, logging
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram_partner_code_reliable")
MAX_CODE_REQUESTS = 10
TEHRAN = ZoneInfo("Asia/Tehran")


def install(app, B):
    if getattr(B, "_partner_code_reliable_installed", False):
        return

    # Install the existing final off-hours/night-worker gate from the active
    # runtime. Its handlers are below the early /start and language guards but
    # still before ordinary business handlers.
    try:
        import telegram_offhours_partner_gate_v2 as OFF
        OFF.install(app, B)
    except Exception:
        log.exception("off-hours gate unavailable")

    def is_open():
        try:
            op = str(B.db.setting("work_open", "07:00") or "07:00")
            cl = str(B.db.setting("work_close", "19:00") or "19:00")
            from datetime import time
            o, c = time.fromisoformat(op), time.fromisoformat(cl)
            now = datetime.now(TEHRAN).time()
            return o <= now < c if o < c else (now >= o or now < c)
        except Exception:
            return False

    def allowed_closed(uid):
        try:
            import telegram_offhours_partner_gate_v2 as OFF
            return bool(OFF._allowed_during_closed(B, uid))
        except Exception:
            try:
                return bool(B.admin(uid))
            except Exception:
                return False

    def closed_markup():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 شروع مجدد", callback_data="off:restart")],
            [InlineKeyboardButton("👥 پنل همکاران", callback_data="off:partner")],
        ])

    def closed_text():
        return (
            "⏰ ربات در حال حاضر خارج از ساعت کاری است.\n\n"
            "🕖 ساعت کاری: ۷ صبح تا ۷ شب به وقت تهران\n"
            "🚫 در این زمان هیچ‌یک از خدمات عادی، دریافت اطلاعات یا ادامه درخواست‌ها فعال نیست.\n\n"
            "فقط همکارانی که در پنل مدیریت برای شیفت شب تعریف شده‌اند می‌توانند از پنل همکاران استفاده کنند."
        )

    # Authoritative /start guard. This is earlier than every legacy startup
    # handler, so the night lock also applies to /start.
    async def start_guard(update, context):
        uid = getattr(getattr(update, "effective_user", None), "id", None)
        if uid is None:
            return
        if not is_open() and not allowed_closed(uid):
            msg = getattr(update, "effective_message", None)
            if msg:
                await msg.reply_text(closed_text(), reply_markup=closed_markup())
            raise ApplicationHandlerStop
        return await B.start(update, context)

    # Legacy language buttons are never allowed to switch Telegram away from
    # Persian. They are converted into the Persian service entry point.
    async def language_guard(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        data = str(q.data or "").strip()
        if not (data.startswith("lang:") or data.startswith("language:")):
            return
        await q.answer("زبان ربات فارسی است.")
        uid = q.from_user.id
        B.S.setdefault(uid, {})["lang"] = "fa"
        await q.message.reply_text(
            "لطفاً از دکمه «🛎 استفاده از خدمات» استفاده کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛎 استفاده از خدمات", callback_data="start:services")]])
        )
        raise ApplicationHandlerStop

    # These groups deliberately precede the legacy startup firewall (-1000000)
    # and the canonical /start handler (-10000000 is not a callback/message
    # conflict because this handler is the only /start command guard).
    app.add_handler(CommandHandler("start", start_guard), group=-2000000)
    app.add_handler(CallbackQueryHandler(language_guard, pattern=r"^(lang|language):"), group=-2000001)

    def exact_chat(rid):
        try:
            import request_language_actions as L
            x = L.request_chat(B.db, rid)
            if x:
                return int(x)
        except Exception:
            pass
        try:
            x = B.db.setting(f"request_chat_{rid}", "").strip()
            return int(x) if x else None
        except Exception:
            return None

    def request_details(rid):
        rows = B.db.conn.execute(
            "SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)
        ).fetchall()
        lines = []
        labels = {
            "phone":"📱 شماره موبایل مشترک", "mobile":"📱 شماره موبایل مشترک",
            "customer_phone":"📱 شماره موبایل مشترک", "subscriber_phone":"📱 شماره موبایل مشترک",
            "dob":"🎂 تاریخ تولد مشترک", "birth_date":"🎂 تاریخ تولد مشترک",
            "unique_id":"🆔 شناسه یکتا", "unique_code":"🆔 شناسه یکتا",
            "special_id":"🔖 شناسه اختصاصی", "special_code":"🔖 شناسه اختصاصی",
            "family_code":"👨‍👩‍👧‍👦 کد خانوار", "household_code":"👨‍👩‍👧‍👦 کد خانوار",
            "passport":"🛂 شماره پاسپورت", "passport_number":"🛂 شماره پاسپورت",
            "doc_type":"🪪 نوع مدرک", "name":"👤 نام و نام خانوادگی", "full_name":"👤 نام و نام خانوادگی",
        }
        for a in rows:
            key = str(a["field_key"] or "")
            ans = str(a["answer"] or "").strip()
            fid = str(a["file_id"] or "").strip()
            if ans:
                lines.append(f"{labels.get(key, '📋 ' + key)}: {ans}")
            if fid:
                lines.append(f"📎 پیوست {labels.get(key, key)}")
        return "\n".join(lines) if lines else "• اطلاعات تکمیلی ثبت نشده است."

    async def ask(update, context):
        q = update.callback_query
        data = str(q.data or "")
        if not (data.startswith("panel:askcode:") or data.startswith("rq:ask:")):
            return
        if not B.admin(q.from_user.id):
            await q.answer("دسترسی ندارید", show_alert=True)
            raise ApplicationHandlerStop
        try:
            rid = int(data.rsplit(":", 1)[1])
            r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if not r:
                await q.answer("درخواست پیدا نشد", show_alert=True)
                raise ApplicationHandlerStop
            chat = exact_chat(rid)
            if not chat:
                await q.answer("❌ حساب تلگرام ثبت‌کننده این درخواست مشخص نیست.", show_alert=True)
                raise ApplicationHandlerStop
            n = int(B.db.setting(f"partner_code_attempts_{rid}", "0") or 0)
            if n >= MAX_CODE_REQUESTS:
                await q.answer("سقف درخواست کد تکمیل شده است.", show_alert=True)
                raise ApplicationHandlerStop
            n += 1
            for k, v in (
                (f"partner_code_attempts_{rid}", str(n)),
                (f"partner_code_request_admin_{rid}", str(q.from_user.id)),
                (f"request_code_chat_{rid}", str(chat)),
            ):
                B.db.set_setting(k, v)
            B.db.conn.execute(
                "UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
            st = B.S.setdefault(int(q.from_user.id), {})
            st["mode"] = "admin_send_code_image"
            st["code_request_rid"] = rid
            st["code_request_chat"] = int(chat)
            st["lang"] = "fa"
            await q.answer("تصویر را ارسال کنید")
            await q.message.reply_text(
                "🖼️ تصویر یا اسکرین‌شات امنیتی را همین‌جا ارسال کنید.\n\n"
                "بعد از دریافت، تصویر فقط برای همان همکارِ ثبت‌کننده درخواست ارسال می‌شود.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ لغو", callback_data=f"pc:x:{rid}")],
                    [InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت", callback_data="adm:menu")],
                ]),
            )
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("ask partner code failed")
            await q.answer("❌ درخواست کد ناموفق بود.", show_alert=True)
        raise ApplicationHandlerStop

    async def admin_media(update, context):
        msg = update.message
        if not msg:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "admin_send_code_image" or not st.get("code_request_rid"):
            return
        rid = int(st["code_request_rid"])
        chat = int(st.get("code_request_chat") or 0)
        if not chat:
            await msg.reply_text("❌ حساب همکار برای این درخواست مشخص نیست.")
            raise ApplicationHandlerStop
        try:
            caption = (
                "🔐 درخواست کد امنیتی\n\n"
                "این تصویر از طرف مدیریت ارسال شده است. لطفاً کد امنیتی نمایش‌داده‌شده را دریافت کنید "
                "و فقط خودِ کد را در همین چت ارسال کنید."
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f"pc:x:{rid}")]])
            if msg.photo:
                await context.bot.send_photo(chat_id=chat, photo=msg.photo[-1].file_id, caption=caption, reply_markup=kb)
            elif msg.document:
                await context.bot.send_document(chat_id=chat, document=msg.document.file_id, caption=caption, reply_markup=kb)
            else:
                await msg.reply_text("❌ فقط تصویر یا فایل تصویر را ارسال کنید.")
                raise ApplicationHandlerStop
            B.db.set_setting(f"partner_code_image_sent_{rid}", "1")
            pst = B.S.setdefault(chat, {})
            pst["mode"] = "partner_send_code"
            pst["code_request_rid"] = rid
            pst["code_request_admin"] = str(uid)
            pst["lang"] = "fa"
            st["mode"] = None
            st.pop("code_request_rid", None)
            st.pop("code_request_chat", None)
            await msg.reply_text("✅ تصویر برای همان همکار ارسال شد.\n⏳ منتظر کد امنیتی هستیم؛ همکار باید فقط کد را ارسال کند.")
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("send security image failed")
            await msg.reply_text("❌ ارسال تصویر به همکار انجام نشد. دوباره تلاش کنید.")
        raise ApplicationHandlerStop

    async def reply(update, context):
        if not update.message or not update.message.text:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "partner_send_code" or not st.get("code_request_rid"):
            return
        rid = int(st["code_request_rid"])
        text = update.message.text.strip()
        r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        if not r:
            st["mode"] = None
            raise ApplicationHandlerStop
        exact = exact_chat(rid)
        if exact and int(exact) != int(uid):
            return
        if not text or len(text) > 200:
            return
        B.db.answer(rid, "partner_code", answer=text)
        B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.commit()
        aid = str(B.db.setting(f"partner_code_request_admin_{rid}", "")).strip()
        recipients = [aid] if aid else [str(x) for x in B.ADM]
        details = request_details(rid)
        out = (
            "🔐 کد امنیتی از همان حساب ثبت‌کننده دریافت شد\n\n"
            f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n"
            f"📱 حساب تلگرام ثبت‌کننده: {uid}\n\n📋 اطلاعات کامل درخواست:\n{details}\n\n"
            f"🔑 کد امنیتی: {text}"
        )
        sent = False
        for x in recipients:
            if not x:
                continue
            for i in range(3):
                try:
                    await context.bot.send_message(chat_id=int(x), text=out)
                    sent = True
                    break
                except Exception:
                    if i < 2:
                        await asyncio.sleep(.7 * (i + 1))
        B.db.set_setting(f"partner_code_request_admin_{rid}", "")
        B.db.set_setting(f"request_code_chat_{rid}", "")
        st["mode"] = None
        st.pop("code_request_rid", None)
        st.pop("code_request_admin", None)
        await update.message.reply_text(
            "✅ کد دریافت شد و برای همان مدیر درخواست‌کننده ارسال شد." if sent else "⚠️ کد دریافت شد، اما اعلان مدیریت ارسال نشد.",
            reply_markup=B.partner_kb("fa"),
        )
        raise ApplicationHandlerStop

    async def cancel(update, context):
        q = update.callback_query
        data = str(q.data or "")
        if not data.startswith("pc:x:"):
            return
        if not B.admin(q.from_user.id):
            return
        rid = int(data.rsplit(":", 1)[1])
        st = B.S.setdefault(int(q.from_user.id), {})
        st["mode"] = None
        st.pop("code_request_rid", None)
        st.pop("code_request_chat", None)
        B.db.set_setting(f"partner_code_request_admin_{rid}", "")
        B.db.set_setting(f"request_code_chat_{rid}", "")
        await q.answer("لغو شد")
        await q.edit_message_text("❌ درخواست کد لغو شد.")
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(ask, pattern=r"^(panel:askcode|rq:ask):\d+$"), group=-200)
    app.add_handler(CallbackQueryHandler(cancel, pattern=r"^pc:x:\d+$"), group=-201)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, admin_media), group=-200)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply), group=-200)
    B._partner_code_reliable_installed = True
