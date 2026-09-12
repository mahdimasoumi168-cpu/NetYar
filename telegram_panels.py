"""Clean Telegram panel enhancements."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger("netyar.telegram.panels")


def partner_keyboard(B):
    return B.kb([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        ["🎫 درخواست‌های من", "🔎 پیگیری کد"],
        ["📋 سوابق", "💰 موجودی"],
        ["📨 ارسال پیام به مدیریت"],
        ["🚪 خروج از پنل"],
        [B.CANCEL],
    ])


def admin_keyboard(B):
    return B.kb([
        ["👤 پنل کاربران", "👥 همکاران"],
        ["💰 شارژها", "💳 پرداخت‌های مشتری"],
        ["📋 درخواست‌ها", "⚙️ قیمت‌ها"],
        ["📊 گزارش", "🤖 بات‌های متصل"],
        ["📨 پیام‌های مدیریت"],
        ["⬅️ منوی اصلی"],
    ])


def _partner_id(B, uid):
    return B.S.get(uid, {}).get("partner_id")


def _ticket_button(partner_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ پاسخ پیام", callback_data=f"ticket:reply:{partner_id}")]
    ])


def _partner_chat(B, pid):
    try:
        value = B.db.setting(f"partner_chat_{pid}", "")
        return int(value) if value else None
    except Exception:
        return None


async def _partner_requests(update, context, B):
    uid = update.effective_user.id
    pid = _partner_id(B, uid)
    if not pid:
        return
    rows = B.db.conn.execute(
        "SELECT id,tracking_code,service_key,status,amount,payment_status,created_at "
        "FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 30", (pid,)
    ).fetchall()
    if not rows:
        return await update.message.reply_text("🎫 درخواست‌های من\n\nهنوز درخواستی ثبت نشده است.", reply_markup=partner_keyboard(B))
    text = "🎫 درخواست‌های من\n\n" + "\n".join(
        f"#{r['id']} | {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount'] or 0):,} تومان"
        for r in rows
    )
    buttons = [[InlineKeyboardButton(f"🔎 {r['tracking_code']}", callback_data=f"panel:req:{r['id']}")] for r in rows[:15]]
    return await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def _partner_balance(update, context, B):
    uid = update.effective_user.id
    pid = _partner_id(B, uid)
    if not pid:
        return
    p = B.db.conn.execute("SELECT name,phone,balance,active FROM partners WHERE id=?", (pid,)).fetchone()
    if not p:
        return await update.message.reply_text("❌ حساب همکار پیدا نشد.", reply_markup=B.main(uid))
    return await update.message.reply_text(
        f"💰 موجودی حساب همکار\n\n👤 {p['name']}\n📱 {p['phone']}\n💳 موجودی: {int(p['balance'] or 0):,} تومان",
        reply_markup=partner_keyboard(B),
    )


async def _partner_message(update, context, B):
    uid = update.effective_user.id
    pid = _partner_id(B, uid)
    if not pid:
        return
    B.S[uid]["mode"] = "partner_message"
    return await update.message.reply_text(
        "📨 پیام خود را برای مدیریت ارسال کنید.\n\nمشکل یا درخواست خود را کامل بنویسید.",
        reply_markup=B.cancel_kb(),
    )


async def _panel_text(update, context, B):
    t = (update.message.text or "").strip()
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})

    if st.get("mode") == "partner_message":
        pid = st.get("partner_id")
        p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
        if p and t:
            text = f"📨 پیام جدید همکار\n👤 {p['name']}\n📱 {p['phone']}\n🆔 شناسه همکار: {pid}\n\n📝 {t}"
            B.db.set_setting(f"ticket_admin_{pid}", str(next(iter(B.ADM), "")))
            for aid in B.ADM:
                try:
                    await context.bot.send_message(chat_id=int(aid), text=text, reply_markup=_ticket_button(pid))
                except Exception:
                    log.exception("forward partner ticket")
            st["mode"] = None
            return await update.message.reply_text("✅ پیام شما برای مدیریت ارسال شد.\nمدیریت می‌تواند از گزینه «پاسخ پیام» با شما گفتگو کند.", reply_markup=partner_keyboard(B))

    if st.get("mode") == "ticket_admin_reply" and B.admin(uid):
        pid = st.get("ticket_partner_id")
        chat_id = _partner_chat(B, pid)
        if not chat_id or not t:
            return await update.message.reply_text("❌ ارتباط با همکار پیدا نشد.", reply_markup=admin_keyboard(B))
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👔 پاسخ مدیریت\n\n{t}",
                reply_markup=_ticket_button(pid),
            )
            B.db.set_setting(f"ticket_admin_{pid}", str(uid))
            st["mode"] = None
            st.pop("ticket_partner_id", None)
            return await update.message.reply_text("✅ پاسخ برای همکار ارسال شد.", reply_markup=admin_keyboard(B))
        except Exception:
            log.exception("send admin ticket reply")
            return await update.message.reply_text("❌ ارسال پاسخ انجام نشد.", reply_markup=admin_keyboard(B))

    if st.get("mode") == "ticket_partner_reply" and st.get("partner_id"):
        pid = st.get("partner_id")
        admin_id = B.db.setting(f"ticket_admin_{pid}", "").strip()
        if not admin_id:
            admin_id = str(next(iter(B.ADM), ""))
        if not admin_id or not t:
            return await update.message.reply_text("❌ مدیریت برای پاسخ در دسترس نیست.", reply_markup=partner_keyboard(B))
        p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (pid,)).fetchone()
        text = f"📨 پاسخ همکار\n👤 {p['name'] if p else '-'}\n📱 {p['phone'] if p else '-'}\n\n📝 {t}"
        try:
            await context.bot.send_message(chat_id=int(admin_id), text=text, reply_markup=_ticket_button(pid))
            st["mode"] = None
            return await update.message.reply_text("✅ پاسخ شما برای مدیریت ارسال شد.", reply_markup=partner_keyboard(B))
        except Exception:
            log.exception("send partner ticket reply")
            return await update.message.reply_text("❌ ارسال پاسخ انجام نشد.", reply_markup=partner_keyboard(B))

    if t == "🎫 درخواست‌های من":
        return await _partner_requests(update, context, B)
    if t == "💰 موجودی":
        return await _partner_balance(update, context, B)
    if t == "📨 ارسال پیام به مدیریت":
        return await _partner_message(update, context, B)
    if t == "📨 پیام‌های مدیریت" and B.admin(uid):
        return await update.message.reply_text("📨 پیام‌های مدیریت\n\nبرای پاسخ به پیام‌های همکاران، روی «↩️ پاسخ پیام» بزنید.", reply_markup=admin_keyboard(B))
    return None


async def _panel_media(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("mode") != "partner_message" or not st.get("partner_id"):
        return None
    p = B.db.conn.execute("SELECT name,phone FROM partners WHERE id=?", (st["partner_id"],)).fetchone()
    if not p:
        return None
    caption = update.message.caption or ""
    text = f"📨 پیام جدید همکار\n👤 {p['name']}\n📱 {p['phone']}\n🆔 شناسه همکار: {st['partner_id']}\n\n{caption or 'پیام رسانه‌ای'}"
    for aid in B.ADM:
        try:
            markup = _ticket_button(st["partner_id"])
            if update.message.photo:
                await context.bot.send_photo(chat_id=int(aid), photo=update.message.photo[-1].file_id, caption=text, reply_markup=markup)
            elif update.message.document:
                await context.bot.send_document(chat_id=int(aid), document=update.message.document.file_id, caption=text, reply_markup=markup)
        except Exception:
            log.exception("forward partner media")
    st["mode"] = None
    return await update.message.reply_text("✅ پیام شما برای مدیریت ارسال شد.", reply_markup=partner_keyboard(B))


async def _ticket_callback(update, context, B):
    q = update.callback_query
    data = str(q.data or "")
    if not data.startswith("ticket:reply:"):
        return
    await q.answer()
    try:
        pid = int(data.rsplit(":", 1)[1])
    except Exception:
        return await q.message.reply_text("❌ شناسه همکار نامعتبر است.")
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})

    if B.admin(uid):
        if not _partner_chat(B, pid):
            return await q.message.reply_text("❌ چت همکار ثبت نشده است. همکار باید یک‌بار وارد پنل شود.")
        st["mode"] = "ticket_admin_reply"
        st["ticket_partner_id"] = pid
        B.db.set_setting(f"ticket_admin_{pid}", str(uid))
        return await q.message.reply_text("✍️ پاسخ خود را برای این همکار بنویسید:", reply_markup=B.cancel_kb())

    if st.get("partner_id") != pid:
        return await q.message.reply_text("❌ این پیام مربوط به حساب شما نیست.")
    st["mode"] = "ticket_partner_reply"
    return await q.message.reply_text("✍️ پاسخ خود را برای مدیریت بنویسید:", reply_markup=B.cancel_kb())


async def _panel_callback(update, context, B):
    q = update.callback_query
    data = q.data or ""
    if not data.startswith("panel:"):
        return
    await q.answer()
    parts = data.split(":")
    if parts[1] == "req":
        rid = int(parts[2])
        r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        if not r:
            return await q.message.reply_text("❌ درخواست پیدا نشد.")
        if not B.admin(q.from_user.id) and B.S.get(q.from_user.id, {}).get("partner_id") != r["user_id"]:
            return
        answers = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
        lines = [f"🎫 {r['tracking_code']}", f"🧾 {r['service_key']}", f"📌 وضعیت: {r['status']}", f"💰 مبلغ: {int(r['amount'] or 0):,} تومان", f"💳 پرداخت: {r['payment_status']}", "", "📋 اطلاعات درخواست:"]
        for a in answers:
            if a["answer"]:
                lines.append(f"• {a['field_key']}: {a['answer']}")
        buttons = []
        if B.admin(q.from_user.id):
            buttons = [
                [InlineKeyboardButton("📨 درخواست کد از همکار", callback_data=f"panel:askcode:{rid}")],
                [InlineKeyboardButton("✅ تأیید انجام خدمت", callback_data=f"panel:approve:{rid}"), InlineKeyboardButton("❌ رد درخواست", callback_data=f"panel:reject:{rid}")],
                [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"panel:review:{rid}"), InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
            ]
        await q.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)
        for a in answers:
            if not a["file_id"]:
                continue
            try:
                if str(a["field_key"]).startswith("file_"):
                    await q.message.reply_document(document=a["file_id"], caption=f"📎 {a['field_key']}")
                else:
                    await q.message.reply_photo(photo=a["file_id"], caption=f"📎 {a['field_key']}")
            except Exception:
                log.exception("send request attachment")
        return
    if not B.admin(q.from_user.id):
        return
    rid = int(parts[2])
    r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    if not r:
        return await q.message.reply_text("❌ درخواست پیدا نشد.", reply_markup=admin_keyboard(B))
    status = {"approve": "completed", "reject": "rejected", "review": "processing"}.get(parts[1])
    if not status:
        return
    B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (status, B.now(), rid))
    B.db.conn.commit()
    user = B.db.conn.execute("SELECT external_id,platform FROM users WHERE id=?", (r["user_id"],)).fetchone()
    if user and user["platform"] == "telegram":
        msg = {"completed": "✅ درخواست شما انجام شد.", "rejected": "❌ درخواست شما رد شد.", "processing": "⏳ درخواست شما در حال بررسی است."}[status]
        try:
            await context.bot.send_message(chat_id=int(user["external_id"]), text=f"{msg}\n🎫 کد پیگیری: {r['tracking_code']}", reply_markup=B.main(int(user["external_id"])))
        except Exception:
            log.exception("notify customer")
    return await q.message.reply_text(f"✅ وضعیت درخواست به «{status}» تغییر کرد.", reply_markup=admin_keyboard(B))


def install(app, B):
    B.partner_kb = lambda lang="fa": partner_keyboard(B)
    B.amenu = lambda: admin_keyboard(B)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: _panel_text(u,c,B)), group=-1)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, lambda u,c: _panel_media(u,c,B)), group=-1)
    app.add_handler(CallbackQueryHandler(lambda u,c: _ticket_callback(u,c,B), pattern=r"^ticket:reply:"), group=-1)
    app.add_handler(CallbackQueryHandler(lambda u,c: _panel_callback(u,c,B), pattern=r"^panel:"), group=-1)
