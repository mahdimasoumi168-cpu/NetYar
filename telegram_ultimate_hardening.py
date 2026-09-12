"""Last Telegram safety layer.

This layer is intentionally additive: it intercepts only known problematic
states/callbacks and delegates everything else to the existing runtime.
"""
import logging
import re
import secrets
from types import SimpleNamespace
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.ultimate_hardening")


def _fake(update, text):
    q = update.callback_query
    src = q.message
    class Msg:
        def __init__(self, original, value):
            self._original = original
            self.text = value
        def __getattr__(self, name):
            return getattr(self._original, name)
    msg = Msg(src, text)
    return SimpleNamespace(update_id=getattr(update, "update_id", None), message=msg,
                           effective_message=msg, effective_user=update.effective_user,
                           effective_chat=getattr(update, "effective_chat", None), callback_query=q)


def _clean(s):
    return str(s or "").strip()


def _ik_label(data, q):
    try:
        import telegram_no_reply_keyboard as N
        v = N._ACTIONS.get(data)
        if v:
            return _clean(v)
    except Exception:
        pass
    try:
        for row in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
            for b in row:
                if str(getattr(b, "callback_data", "")) == data:
                    return _clean(getattr(b, "text", ""))
    except Exception:
        pass
    return ""


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


async def _callback(update, context, B):
    q = update.callback_query
    data = _clean(q.data)
    if not (data.startswith("ik:") or data.startswith("ui:")):
        return
    await q.answer()
    label = _ik_label(data, q) if data.startswith("ik:") else data[3:]
    if not label:
        await q.message.reply_text("❌ این دکمه دیگر معتبر نیست؛ لطفاً از منوی فعلی استفاده کنید.")
        raise ApplicationHandlerStop
    fake = _fake(update, label)
    if label in {B.CANCEL, "❌ لغو", "Cancel", "❌ Cancel", "إلغاء", "❌ إلغاء"}:
        # Never let the ticket free-form handler see the cancel label.
        await B.cancel(fake, context)
        raise ApplicationHandlerStop
    try:
        result = await B.router(fake, context)
        if result is not None:
            raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("Telegram callback failed: %s", label)
        await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
        raise ApplicationHandlerStop


async def _ticket_reply(update, context, B):
    q = update.callback_query
    data = _clean(q.data)
    if not data.startswith("ticket:reply:"):
        return
    await q.answer()
    try:
        pid = int(data.rsplit(":", 1)[1])
    except Exception:
        await q.message.reply_text("❌ شناسه تیکت نامعتبر است.")
        raise ApplicationHandlerStop
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})
    if B.admin(uid):
        st["mode"] = "ticket_admin_reply"
        st["ticket_partner_id"] = pid
    else:
        if st.get("partner_id") and int(st["partner_id"]) != pid:
            await q.message.reply_text("❌ این تیکت متعلق به شما نیست.")
            raise ApplicationHandlerStop
        st["partner_id"] = pid
        st["mode"] = "ticket_partner_reply"
    await q.message.reply_text("💬 پاسخ به تیکت فعال شد.\nپیام خود را بفرستید.\nبرای خروج، «❌ انصراف» را بزنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
    raise ApplicationHandlerStop


async def _topup_entry(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if not st.get("partner_id"):
        return await update.message.reply_text("❌ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
    st["mode"] = "topup_amount"
    st.pop("topup_amount", None)
    return await update.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:\nمثال: 500000", reply_markup=B.cancel_kb(st.get("lang", "fa")))


async def _topup_amount(update, context, B):
    st = B.S.setdefault(update.effective_user.id, {})
    if st.get("mode") != "topup_amount":
        return
    raw = _digits(update.message.text).replace(",", "").replace("٬", "").replace("تومان", "").replace(" ", "")
    if not raw.isdigit() or int(raw) <= 0:
        return await update.message.reply_text("❌ مبلغ نامعتبر است. فقط عدد وارد کنید؛ مثال: 500000", reply_markup=B.cancel_kb(st.get("lang", "fa")))
    pid = st.get("partner_id")
    p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
    if not p:
        st["mode"] = None
        return await update.message.reply_text("❌ حساب همکار پیدا نشد.", reply_markup=B.main(update.effective_user.id))
    st["topup_amount"] = int(raw)
    st["mode"] = "topup_receipt"
    return await update.message.reply_text(f"💰 مبلغ شارژ: {int(raw):,} تومان\n\n📎 حالا تصویر یا فایل رسید واریز را ارسال کنید.\nبعد از دریافت رسید، درخواست برای مدیریت ارسال می‌شود.", reply_markup=B.cancel_kb(st.get("lang", "fa")))


async def _gov_text(update, context, B, old):
    st = B.S.setdefault(update.effective_user.id, {})
    mode = st.get("mode")
    text = _clean(update.message.text)
    digits = _digits(text).replace(" ", "").replace("-", "")
    lang = st.get("lang", "fa")
    if mode == "gov_special":
        if len(digits) < 3:
            return await update.message.reply_text("❌ شناسه اختصاصی را صحیح وارد کنید.", reply_markup=B.cancel_kb(lang))
        st["gov_special"] = digits
        st.pop("gov_family_code", None)
        st["mode"] = "gov_identity"
        prompt = "🛂 شماره پاسپورت/گذرنامه مشترک را وارد کنید:" if st.get("gov_doc_type") == "passport" else "📗 شماره دفترچه اقامت مشترک را وارد کنید:"
        return await update.message.reply_text(prompt, reply_markup=B.cancel_kb(lang))
    if mode in {"gov_identity", "gov_family", "gov_passport"}:
        if len(digits) < 3:
            return await update.message.reply_text("❌ شماره مدرک را صحیح وارد کنید.", reply_markup=B.cancel_kb(lang))
        if st.get("gov_doc_type") == "passport":
            st["gov_passport"] = text
        else:
            st["booklet_number"] = digits
        st.pop("gov_family_code", None)
        st["mode"] = "gov_postal"
        return await update.message.reply_text("📮 حالا کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=B.cancel_kb(lang))
    if mode == "gov_postal":
        if not re.fullmatch(r"\d{10}", digits):
            return await update.message.reply_text("❌ کد پستی منزل باید دقیقاً ۱۰ رقم باشد.", reply_markup=B.cancel_kb(lang))
        st["postal_code"] = digits
        st["mode"] = "gov_photo"
        return await update.message.reply_text("📸 حالا عکس مدرک مشترک را ارسال کنید.", reply_markup=B.cancel_kb(lang))
    return await old(update, context)


async def _gov_media(update, context, B, old):
    st = B.S.setdefault(update.effective_user.id, {})
    if st.get("mode") != "gov_photo" or not st.get("partner_id"):
        return await old(update, context)
    msg = update.message
    fid = msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
    if not fid:
        return await msg.reply_text("❌ عکس یا فایل معتبر ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
    pid = int(st["partner_id"])
    amount = int(B.db.setting("price_government", "500000") or 500000)
    conn = B.db.conn
    try:
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        p = conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
        balance = int(p["balance"] or 0) if p else 0
        if not p or balance < amount:
            conn.rollback()
            return await msg.reply_text(f"❌ اعتبار کافی نیست.\n💰 هزینه خدمت: {amount:,} تومان\n💳 اعتبار فعلی: {balance:,} تومان", reply_markup=B.partner_kb(st.get("lang", "fa")))
        code = "NYM-" + secrets.token_hex(4).upper()
        t = B.now()
        cur = conn.execute("INSERT INTO requests(tracking_code,user_id,service_key,platform,status,amount,payment_status,payment_method,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (code,pid,"government","telegram","submitted",amount,"paid","partner_balance",t,t))
        rid = cur.lastrowid
        fields = [("doc_type",st.get("gov_doc_type","")),("phone",st.get("gov_phone",st.get("phone",""))), ("dob",st.get("dob","")), ("unique_id",st.get("gov_unique",st.get("unique_id",""))), ("special_id",st.get("gov_special",st.get("special_id",""))), ("postal_code",st.get("postal_code",""))]
        if st.get("gov_doc_type") == "passport":
            fields.append(("passport",st.get("gov_passport","")))
        else:
            fields.append(("booklet_number",st.get("booklet_number","")))
        for key,value in fields:
            if value: conn.execute("INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)", (rid,key,str(value),"",t))
        conn.execute("INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)", (rid,"document","",fid,t))
        cur = conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=? AND balance>=?", (amount,t,pid,amount))
        if cur.rowcount != 1:
            raise RuntimeError("partner balance changed during charge")
        conn.commit()
        left = balance - amount
    except Exception:
        try: conn.rollback()
        except Exception: pass
        log.exception("atomic government credit charge failed")
        return await msg.reply_text("❌ ثبت درخواست انجام نشد و هیچ مبلغی از اعتبار کسر نشد. لطفاً دوباره تلاش کنید.", reply_markup=B.partner_kb(st.get("lang", "fa")))
    text = f"🆕 درخواست سامانه دولت من\n🎫 کد پیگیری: {code}\n🪪 نوع مدرک: {st.get('gov_doc_type','-')}\n📱 موبایل مشترک: {st.get('gov_phone',st.get('phone','-'))}\n🎂 تاریخ تولد: {st.get('dob','-')}\n🆔 شناسه یکتا: {st.get('gov_unique',st.get('unique_id','-'))}\n🔖 شناسه اختصاصی: {st.get('gov_special',st.get('special_id','-'))}\n" + (f"🛂 شماره پاسپورت: {st.get('gov_passport','-')}\n" if st.get('gov_doc_type') == 'passport' else f"📗 شماره دفترچه: {st.get('booklet_number','-')}\n") + f"📮 کد پستی: {st.get('postal_code','-')}\n💰 مبلغ کسرشده: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان\n📎 مدرک پیوست شده است."
    try:
        await B.notify_admins(context.application, text, rid)
    except Exception:
        log.exception("government admin notification failed")
    st["mode"] = None
    st.pop("gov_family_code", None)
    return await msg.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ کسرشده: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان", reply_markup=B.partner_kb(st.get("lang", "fa")))


def install(app, B):
    if getattr(B, "_telegram_ultimate_hardening", False):
        return
    try:
        import final_safety_patch
        final_safety_patch.install()
    except Exception:
        log.exception("final_safety_patch install failed")
    old_topup = getattr(B, "topup", None)
    if old_topup:
        B.topup = lambda update, context: _topup_entry(update, context, B)
    old_service_text = getattr(B, "service_text", None)
    if old_service_text:
        async def service_text(update, context):
            if B.S.get(update.effective_user.id, {}).get("mode") == "topup_amount":
                return await _topup_amount(update, context, B)
            return await old_service_text(update, context)
        B.service_text = service_text
    old_gov_text = getattr(B, "gov_text", None)
    if old_gov_text:
        async def gov_text(update, context):
            return await _gov_text(update, context, B, old_gov_text)
        B.gov_text = gov_text
    old_media = getattr(B, "media", None)
    if old_media:
        async def media(update, context):
            return await _gov_media(update, context, B, old_media)
        B.media = media
    app.add_handler(CallbackQueryHandler(lambda u,c: _callback(u,c,B), pattern=r"^(ik:|ui:)"), group=-170)
    app.add_handler(CallbackQueryHandler(lambda u,c: _ticket_reply(u,c,B), pattern=r"^ticket:reply:"), group=-169)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: _topup_amount(u,c,B)), group=-168)
    B._telegram_ultimate_hardening = True
    log.info("Telegram ultimate hardening installed")
