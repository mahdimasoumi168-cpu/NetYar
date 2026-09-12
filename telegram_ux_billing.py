"""Telegram UX, manager code-request action, and partner billing hardening."""
import re
from types import SimpleNamespace
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters

B = None


def _restart_keyboard():
    return ReplyKeyboardMarkup([["🔄 شروع مجدد"]], resize_keyboard=True, one_time_keyboard=False)


def _inline_kb(rows):
    out = []
    for row in rows or []:
        buttons = []
        for item in row or []:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                label = str(item[1])
            else:
                label = str(item)
            # Visual color cues: Telegram does not expose custom button colors.
            if "پنل همکاران" in label and "🔵" not in label:
                label = "🔵 " + label
            elif label in {"خدمات چاپ", "🖨 خدمات چاپ"} and "🟢" not in label:
                label = "🟢 " + label
            elif "دولت من" in label and "🟠" not in label:
                label = "🟠 " + label
            elif "پیگیری" in label and "🟡" not in label:
                label = "🟡 " + label
            elif "کیف پول" in label and "💰" not in label:
                label = "💰 " + label
            buttons.append(InlineKeyboardButton(label, callback_data="ui:" + label[:180]))
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
    # Partner/admin panel text handlers get first chance; then the canonical router.
    try:
        if "telegram_panels" in globals():
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


async def _gov_postal(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("mode") != "gov_postal":
        return
    text = (update.message.text or "").strip()
    digits = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    if not re.fullmatch(r"\d{10}", digits):
        return await update.message.reply_text("❌ کد پستی منزل باید دقیقاً ۱۰ رقم باشد. دوباره وارد کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
    st["postal_code"] = digits
    st["mode"] = "gov_photo"
    prompt = "📮 کد پستی ثبت شد.\n📸 حالا عکس مدرک مشترک را ارسال کنید."
    return await update.message.reply_text(prompt, reply_markup=B.cancel_kb(st.get("lang", "fa")))


async def _gov_media(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("mode") != "gov_photo":
        return
    fid = update.message.photo[-1].file_id if update.message.photo else (update.message.document.file_id if update.message.document else "")
    if not fid:
        return await update.message.reply_text("❌ عکس یا فایل معتبر ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
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
        ("postal_code", st.get("postal_code", "")),
    ]
    if st.get("gov_doc_type") == "passport":
        fields.append(("passport", st.get("gov_passport", "")))
    for key, value in fields:
        if value:
            B.db.answer(rid, key, answer=value)
    B.db.answer(rid, "document", file_id=fid)
    if pid:
        B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?", (amount, B.now(), pid))
        B.db.conn.commit()
        left = int(p["balance"]) - amount
    else:
        B.db.conn.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.commit()
        left = None
    title = "👔 مدیر — اعلان خدمات جدید"
    text = (
        f"{title}\n\n🆕 حل مشکل سامانه دولت من\n🎫 کد پیگیری: {code}\n"
        f"🪪 نوع مدرک: {st.get('gov_doc_type','-')}\n📱 موبایل مشترک: {st.get('gov_phone',st.get('phone','-'))}\n"
        f"🎂 تاریخ تولد: {st.get('dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique',st.get('unique_id','-'))}\n"
        f"🔖 شناسه اختصاصی: {st.get('gov_special',st.get('special_id','-'))}\n📮 کد پستی منزل: {st.get('postal_code','-')}\n"
        f"💰 مبلغ خدمت: {amount:,} تومان\n"
        + (f"💳 کسر از اعتبار همکار: {amount:,} تومان\n💵 اعتبار باقی‌مانده: {left:,} تومان\n" if pid else "")
        + "📎 مدرک در همین اعلان پیوست شده است."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"panel:req:{rid}")],
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
        reply = f"✅ درخواست با موفقیت ثبت و انجام کار برای مدیریت ارسال شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ کسرشده: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان"
        return await update.message.reply_text(reply, reply_markup=B.partner_kb(st.get("lang", "fa")))
    return await update.message.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}", reply_markup=B.main(uid))


async def _ask_code_callback(update, context):
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("panel:askcode:"):
        return
    await q.answer("درخواست کد برای همکار ارسال شد")
    rid = int(data.split(":")[-1])
    r = B.db.conn.execute("SELECT user_id,tracking_code,service_key FROM requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return await q.message.reply_text("❌ درخواست پیدا نشد.")
    p = B.db.conn.execute("SELECT phone,name FROM partners WHERE id=?", (r["user_id"],)).fetchone()
    if not p:
        return await q.message.reply_text("❌ این درخواست به همکار متصل نیست.")
    rows = B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram'", (r["user_id"],)).fetchone()
    if not rows:
        return await q.message.reply_text("❌ شناسه تلگرام همکار پیدا نشد.")
    partner_uid = rows["external_id"]
    B.S.setdefault(int(partner_uid), {})["mode"] = "partner_send_code"
    try:
        await context.bot.send_message(chat_id=int(partner_uid), text=f"👔 مدیریت\n\n📨 برای درخواست {r['tracking_code']} کد خدمت/کد انجام کار را برای مدیریت ارسال کنید:", reply_markup=_inline_kb([["لغو"]]))
    except Exception:
        return await q.message.reply_text("❌ ارسال درخواست کد به همکار انجام نشد.")
    return await q.message.reply_text(f"✅ درخواست کد برای همکار «{p['name']}» ارسال شد.")


async def _partner_code_text(update, context):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("mode") != "partner_send_code" or not st.get("partner_id"):
        return
    text = (update.message.text or "").strip()
    if not text or text == "لغو":
        st["mode"] = None
        return await update.message.reply_text("❌ ارسال کد لغو شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
    p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (st["partner_id"],)).fetchone()
    for aid in B.ADM:
        try:
            await context.bot.send_message(chat_id=int(aid), text=f"👔 مدیر — کد از همکار دریافت شد\n\n👤 همکار: {p['name'] if p else '-'}\n📱 شماره: {p['phone'] if p else '-'}\n🆔 شناسه تلگرام: {uid}\n🎫 کد خدمت: {text}")
        except Exception:
            pass
    st["mode"] = None
    return await update.message.reply_text("✅ کد خدمت برای مدیریت ارسال شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))


def install(app, bot_module):
    global B
    B = bot_module
    import telegram_panels
    # Inline menus: no persistent Telegram reply keyboard except Restart.
    B.kb = _ui_markup
    B.cancel_kb = lambda lang="fa": _ui_markup([[B.CANCEL]])
    # Make Restart the only persistent bottom keyboard.
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"), _restart), group=-5)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _gov_postal), group=-4)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, _gov_media), group=-4)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _partner_code_text), group=-4)
    app.add_handler(CallbackQueryHandler(_ask_code_callback, pattern=r"^panel:askcode:"), group=-4)
    app.add_handler(CallbackQueryHandler(_ui_callback, pattern=r"^ui:"), group=-4)
    B._telegram_inline_ui_installed = True
