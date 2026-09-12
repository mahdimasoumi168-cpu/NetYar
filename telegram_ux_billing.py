"""Telegram UX, government identity validation, and manager/partner code flow."""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

B = None
telegram_panels = None


def _restart_keyboard():
    return ReplyKeyboardMarkup([["🔄 شروع مجدد"]], resize_keyboard=True, one_time_keyboard=False)


def _inline_kb(rows):
    out = []
    for row in rows or []:
        buttons = []
        for item in row or []:
            original = str(item[1]) if isinstance(item, (tuple, list)) and len(item) >= 2 else str(item)
            label = original
            if "پنل همکاران" in label and "🔵" not in label:
                label = "🔵 " + label
            elif "خدمات چاپ" in label and "🟢" not in label:
                label = "🟢 " + label
            elif "دولت من" in label and "🟠" not in label:
                label = "🟠 " + label
            elif "پیگیری" in label and "🟡" not in label:
                label = "🟡 " + label
            elif "کیف پول" in label and "💰" not in label:
                label = "💰 " + label
            buttons.append(InlineKeyboardButton(label, callback_data="ui:" + original[:180]))
        if buttons:
            out.append(buttons)
    return InlineKeyboardMarkup(out)


def _ui_markup(rows):
    return _inline_kb(rows)


class _MessageProxy:
    def __init__(self, original, text):
        self._original = original
        self.text = text

    def __getattr__(self, name):
        return getattr(self._original, name)


class _UpdateProxy:
    def __init__(self, update, text):
        self._update = update
        self.message = _MessageProxy(update.callback_query.message, text)
        self.effective_user = update.effective_user
        self.effective_chat = update.effective_chat

    def __getattr__(self, name):
        return getattr(self._update, name)


async def _ui_callback(update, context):
    q = update.callback_query
    if not q or not (q.data or "").startswith("ui:"):
        return
    label = q.data[3:]
    await q.answer()
    proxy = _UpdateProxy(update, label)
    try:
        result = await telegram_panels._panel_text(proxy, context, B)
        if result is not None:
            raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception:
        pass
    result = await B.router(proxy, context)
    if result is not None:
        raise ApplicationHandlerStop


async def _restart(update, context):
    if (update.message.text or "").strip() != "🔄 شروع مجدد":
        return
    uid = update.effective_user.id
    B.S[uid] = {}
    return await B.start(update, context)


def _digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


async def _gov_postal(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    text = (update.message.text or "").strip()
    digits = _digits(text).replace(" ", "").replace("-", "")

    if mode == "gov_special":
        if not re.fullmatch(r"1\d{11}", digits):
            return await update.message.reply_text(
                "❌ شناسه اختصاصی صحیح نیست.\nشناسه اختصاصی باید دقیقاً ۱۲ رقم باشد و با عدد ۱ شروع شود.",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        st["gov_special"] = digits
        st["mode"] = "gov_family"
        return await update.message.reply_text(
            "👨‍👩‍👧‍👦 حالا کد خانوار مشترک را وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    if mode == "gov_family":
        if not re.fullmatch(r"\d{1,20}", digits):
            return await update.message.reply_text(
                "❌ کد خانوار باید عددی باشد. دوباره وارد کنید.",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        st["gov_family_code"] = digits
        if st.get("gov_doc_type") == "passport":
            st["mode"] = "gov_passport"
            return await update.message.reply_text(
                "🛂 شماره گذرنامه/پاسپورت مشترک را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        st["mode"] = "gov_postal"
        return await update.message.reply_text(
            "📮 حالا کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    if mode == "gov_passport":
        if len(text) < 3:
            return await update.message.reply_text(
                "❌ شماره گذرنامه را صحیح وارد کنید.",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        st["gov_passport"] = text
        st["mode"] = "gov_postal"
        return await update.message.reply_text(
            "📮 حالا کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    if mode != "gov_postal":
        return
    if not re.fullmatch(r"\d{10}", digits):
        return await update.message.reply_text(
            "❌ کد پستی منزل باید دقیقاً ۱۰ رقم باشد. دوباره وارد کنید.",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )
    st["postal_code"] = digits
    st["mode"] = "gov_photo"
    return await update.message.reply_text(
        "📮 کد پستی ثبت شد.\n📸 حالا عکس مدرک مشترک را ارسال کنید.",
        reply_markup=B.cancel_kb(st.get("lang", "fa")),
    )


async def _gov_media(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("mode") != "gov_photo":
        return
    fid = update.message.photo[-1].file_id if update.message.photo else (update.message.document.file_id if update.message.document else "")
    if not fid:
        return await update.message.reply_text(
            "❌ عکس یا فایل معتبر ارسال کنید.",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    amount = int(B.db.setting("price_government", "500000") or 500000)
    pid = st.get("partner_id")
    p = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone() if pid else None
    if pid and (not p or int(p["balance"] or 0) < amount):
        return await update.message.reply_text(
            f"❌ اعتبار کافی نیست.\n💰 هزینه خدمت: {amount:,} تومان\n💳 اعتبار فعلی: {int(p['balance'] if p else 0):,} تومان\n\nلطفاً ابتدا حساب را شارژ کنید.",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )

    owner = pid or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
    rid, code = B.db.create_request(owner, "government", "telegram", amount)
    fields = [
        ("doc_type", st.get("gov_doc_type", "")),
        ("phone", st.get("gov_phone", st.get("phone", ""))),
        ("dob", st.get("dob", "")),
        ("unique_id", st.get("gov_unique", st.get("unique_id", ""))),
        ("special_id", st.get("gov_special", st.get("special_id", ""))),
        ("family_code", st.get("gov_family_code", "")),
        ("postal_code", st.get("postal_code", "")),
    ]
    if st.get("gov_doc_type") == "passport":
        fields.append(("passport", st.get("gov_passport", "")))
    for key, value in fields:
        if value:
            B.db.answer(rid, key, answer=value)
    B.db.answer(rid, "document", file_id=fid)

    if pid:
        B.db.conn.execute(
            "UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",
            (B.now(), rid),
        )
        B.db.conn.execute(
            "UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",
            (amount, B.now(), pid),
        )
        B.db.conn.commit()
        left = int(p["balance"]) - amount
    else:
        B.db.conn.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.commit()
        left = None

    text = (
        f"👔 مدیر — اعلان خدمات جدید\n\n"
        f"🆕 حل مشکل سامانه دولت من\n"
        f"🎫 کد پیگیری: {code}\n"
        f"🪪 نوع مدرک: {st.get('gov_doc_type','-')}\n"
        f"📱 موبایل مشترک: {st.get('gov_phone',st.get('phone','-'))}\n"
        f"🎂 تاریخ تولد: {st.get('dob','-')}\n"
        f"🆔 شناسه یکتا: {st.get('gov_unique',st.get('unique_id','-'))}\n"
        f"🔖 شناسه اختصاصی: {st.get('gov_special',st.get('special_id','-'))}\n"
        f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family_code','-')}\n"
        f"📮 کد پستی منزل: {st.get('postal_code','-')}\n"
        f"💰 مبلغ خدمت: {amount:,} تومان\n"
        + (f"💳 کسر از اعتبار همکار: {amount:,} تومان\n💵 اعتبار باقی‌مانده: {left:,} تومان\n" if pid else "")
        + "📎 عکس/مدرک مشترک در همین اعلان پیوست شده است."
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده کامل درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"), InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"), InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])

    for aid in B.ADM:
        try:
            if update.message.photo:
                await context.bot.send_photo(chat_id=int(aid), photo=fid, caption=text, reply_markup=markup)
            else:
                await context.bot.send_document(chat_id=int(aid), document=fid, caption=text, reply_markup=markup)
        except Exception:
            pass

    st["mode"] = None
    if pid:
        return await update.message.reply_text(
            f"✅ درخواست با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ کسرشده: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
    return await update.message.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}", reply_markup=B.main(uid))


async def _ask_code_callback(update, context):
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("panel:askcode:"):
        return
    await q.answer("درخواست کد برای همکار ارسال شد")
    if not B.admin(q.from_user.id):
        return
    try:
        rid = int(data.split(":")[-1])
    except ValueError:
        return await q.message.reply_text("❌ شناسه درخواست نامعتبر است.")

    r = B.db.conn.execute(
        "SELECT id,user_id,tracking_code,service_key FROM requests WHERE id=?",
        (rid,),
    ).fetchone()
    if not r:
        return await q.message.reply_text("❌ درخواست پیدا نشد.")

    p = B.db.conn.execute("SELECT phone,name FROM partners WHERE id=?", (r["user_id"],)).fetchone()
    if not p:
        return await q.message.reply_text("❌ این درخواست به همکار متصل نیست.")

    user_row = B.db.conn.execute(
        "SELECT external_id FROM users WHERE id=? AND platform='telegram'",
        (r["user_id"],),
    ).fetchone()
    if not user_row:
        return await q.message.reply_text("❌ شناسه تلگرام همکار پیدا نشد.")

    partner_uid = int(user_row["external_id"])
    partner_state = B.S.setdefault(partner_uid, {})
    partner_state["partner_id"] = r["user_id"]
    partner_state["mode"] = "partner_send_code"
    partner_state["code_request_rid"] = rid
    partner_state["lang"] = partner_state.get("lang", "fa")

    # Persist the pending request so a restart does not lose the manager's request.
    B.db.set_setting(f"partner_code_request_{r['user_id']}", f"{rid}|{r['tracking_code']}")
    B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?", (B.now(), rid))
    B.db.conn.commit()

    message = (
        "👔 مدیریت\n\n"
        f"📨 مدیریت برای درخواست کد خدمت را دارد.\n"
        f"🎫 کد پیگیری: {r['tracking_code']}\n"
        f"🧾 خدمت: {r['service_key']}\n\n"
        "لطفاً کد خدمت/کد انجام کار را همینجا ارسال کنید."
    )
    try:
        await context.bot.send_message(chat_id=partner_uid, text=message)
    except Exception as exc:
        partner_state["mode"] = None
        return await q.message.reply_text(f"❌ ارسال درخواست کد به همکار انجام نشد.\nجزئیات: {exc}")

    return await q.message.reply_text(
        f"✅ درخواست کد برای همکار «{p['name']}» ارسال شد.\n🎫 {r['tracking_code']}"
    )


async def _partner_code_text(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    pid = st.get("partner_id")
    pending = st.get("mode") == "partner_send_code"

    # Recover a pending manager request after a process restart.
    if not pending:
        user_row = B.db.conn.execute(
            "SELECT id FROM users WHERE external_id=? AND platform='telegram'",
            (str(uid),),
        ).fetchone()
        if user_row:
            setting = B.db.setting(f"partner_code_request_{user_row['id']}", "")
            if setting:
                try:
                    rid, tracking = setting.split("|", 1)
                    pid = user_row["id"]
                    st.update(partner_id=pid, mode="partner_send_code", code_request_rid=int(rid))
                    pending = True
                except Exception:
                    pass

    if not pending or not pid:
        return

    text = (update.message.text or "").strip()
    if not text:
        return await update.message.reply_text("❌ کد خالی است؛ کد خدمت را ارسال کنید.")

    rid = st.get("code_request_rid")
    tracking = "-"
    if rid:
        req = B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?", (rid,)).fetchone()
        if req:
            tracking = req["tracking_code"]
            B.db.answer(rid, "partner_code", answer=text)
            B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?", (B.now(), rid))
            B.db.conn.commit()

    p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
    admin_text = (
        "👔 مدیر — کد از همکار دریافت شد\n\n"
        f"👤 همکار: {p['name'] if p else '-'}\n"
        f"📱 شماره: {p['phone'] if p else '-'}\n"
        f"🆔 شناسه تلگرام: {uid}\n"
        f"🎫 کد پیگیری: {tracking}\n"
        f"🔐 کد خدمت: {text}"
    )
    for aid in B.ADM:
        try:
            await context.bot.send_message(chat_id=int(aid), text=admin_text)
        except Exception:
            pass

    B.db.set_setting(f"partner_code_request_{pid}", "")
    st["mode"] = None
    st.pop("code_request_rid", None)
    return await update.message.reply_text(
        "✅ کد خدمت دریافت و برای مدیریت ارسال شد.",
        reply_markup=B.partner_kb(st.get("lang", "fa")),
    )


def install(app, bot_module):
    global B, telegram_panels
    B = bot_module
    import telegram_panels as panels
    telegram_panels = panels
    B.kb = _ui_markup
    B.cancel_kb = lambda lang="fa": _ui_markup([[B.CANCEL]])

    old_start = B.start

    async def start_with_restart(update, context):
        result = await old_start(update, context)
        try:
            await update.message.reply_text("دسترسی سریع:", reply_markup=_restart_keyboard())
        except Exception:
            pass
        return result

    B.start = start_with_restart
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"), _restart), group=-5)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _gov_postal), group=-4)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, _gov_media), group=-4)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _partner_code_text), group=-4)
    app.add_handler(CallbackQueryHandler(_ask_code_callback, pattern=r"^panel:askcode:"), group=-4)
    app.add_handler(CallbackQueryHandler(_ui_callback, pattern=r"^ui:"), group=-4)
    B._telegram_inline_ui_installed = True
