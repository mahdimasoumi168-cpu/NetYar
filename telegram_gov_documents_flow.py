"""Government service document flow: ID document required, SIM-card proof optional."""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters


def _optional_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ ادامه بدون سند سیم‌کارت", callback_data="govsim:skip")]])


def _file_id(message):
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        return message.document.file_id
    return ""


async def _finalize(update, context, B, st, sim_fid=""):
    uid = update.effective_user.id
    amount = int(B.db.setting("price_government", "500000") or 500000)
    pid = st.get("partner_id")
    p = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone() if pid else None
    if pid and (not p or int(p["balance"] or 0) < amount):
        return await update.effective_message.reply_text(
            f"❌ اعتبار کافی نیست.\n💰 هزینه خدمت: {amount:,} تومان\n💳 اعتبار فعلی: {int(p['balance'] if p else 0):,} تومان\n\nلطفاً ابتدا حساب را شارژ کنید.",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
    doc_fid = st.get("gov_document_file_id", "")
    if not doc_fid:
        return await update.effective_message.reply_text("❌ تصویر مدرک شناسایی ثبت نشده است. لطفاً دوباره ارسال کنید.")
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
    B.db.answer(rid, "document", file_id=doc_fid)
    if sim_fid:
        B.db.answer(rid, "sim_card_document", file_id=sim_fid)
    if pid:
        B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?", (amount, B.now(), pid))
        B.db.conn.commit()
        left = int(p["balance"]) - amount
    else:
        B.db.conn.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (B.now(), rid))
        B.db.conn.commit()
        left = None
    text = (
        "👔 مدیر — اعلان خدمات جدید\n\n"
        "🆕 حل مشکل سامانه دولت من\n"
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
        + "🪪 تصویر مدرک شناسایی: پیوست شد\n"
        + ("📱 تصویر سند سیم‌کارت: پیوست شد" if sim_fid else "📱 تصویر سند سیم‌کارت: ارسال نشده (اختیاری)")
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
        [InlineKeyboardButton("📤 آوردن درخواست به آخر چت", callback_data=f"panel:resend:{rid}")],
        [InlineKeyboardButton("🔎 مشاهده کامل درخواست", callback_data=f"panel:req:{rid}")],
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"), InlineKeyboardButton("✅ انجام شد", callback_data=f"panel:approve:{rid}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}"), InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
    ])
    for aid in B.ADM:
        try:
            await context.bot.send_photo(chat_id=int(aid), photo=doc_fid, caption=text, reply_markup=markup)
            if sim_fid:
                await context.bot.send_photo(chat_id=int(aid), photo=sim_fid, caption="📱 تصویر سند سیم‌کارت مشترک (اختیاری)")
        except Exception:
            try:
                await context.bot.send_document(chat_id=int(aid), document=doc_fid, caption=text, reply_markup=markup)
                if sim_fid:
                    await context.bot.send_document(chat_id=int(aid), document=sim_fid, caption="📱 تصویر سند سیم‌کارت مشترک (اختیاری)")
            except Exception:
                pass
    st["mode"] = None
    st.pop("gov_document_file_id", None)
    st.pop("gov_sim_document_file_id", None)
    if pid:
        return await update.effective_message.reply_text(
            f"✅ درخواست با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ کسرشده: {amount:,} تومان\n💳 اعتبار باقی‌مانده: {left:,} تومان",
            reply_markup=B.partner_kb(st.get("lang", "fa")),
        )
    return await update.effective_message.reply_text(f"✅ درخواست ثبت شد.\n🎫 کد پیگیری: {code}", reply_markup=B.main(uid))


async def _media(update, context, B):
    message = update.effective_message
    if not message:
        return
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    mode = st.get("mode")
    fid = _file_id(message)
    if not fid or mode not in {"gov_photo", "gov_sim"}:
        return
    if mode == "gov_photo":
        st["gov_document_file_id"] = fid
        st["mode"] = "gov_sim"
        await message.reply_text(
            "✅ تصویر مدرک شناسایی دریافت شد.\n\n📱 حالا اگر دارید، تصویر سند سیم‌کارت را ارسال کنید.\nاین مدرک اختیاری است؛ اگر ندارید روی «⏭️ ادامه بدون سند سیم‌کارت» بزنید.",
            reply_markup=_optional_kb(),
        )
        raise ApplicationHandlerStop
    await _finalize(update, context, B, st, fid)
    raise ApplicationHandlerStop


async def _skip(update, context, B):
    q = update.callback_query
    if not q or q.data != "govsim:skip":
        return
    await q.answer()
    st = B.S.setdefault(q.from_user.id, {})
    if st.get("mode") != "gov_sim":
        return
    await _finalize(update, context, B, st, "")
    raise ApplicationHandlerStop


def install(app, B):
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, lambda u, c: _media(u, c, B)), group=-6)
    app.add_handler(CallbackQueryHandler(lambda u, c: _skip(u, c, B), pattern=r"^govsim:skip$"), group=-6)
