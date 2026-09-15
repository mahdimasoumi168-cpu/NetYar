"""Guided Telegram admin announcement flow.

Flow: choose text/photo/both -> collect content -> choose whether to add a
button -> choose services or a specific service -> set button label -> send.
This layer intentionally uses its own ann2:* callbacks so legacy announcement
handlers cannot collide with the new state machine.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

PREFIX = "ann2:"


def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows])


def _users(B):
    return B.db.conn.execute("SELECT external_id FROM users WHERE platform='telegram' AND external_id IS NOT NULL").fetchall()


def _service_rows(B):
    rows = B.db.conn.execute("SELECT key,name FROM services WHERE active=1 ORDER BY id").fetchall()
    return rows


def _choose_content():
    return _kb([
        [("📝 فقط متن", PREFIX + "type:text"), ("🖼 فقط عکس", PREFIX + "type:photo")],
        [("📝🖼 متن + عکس", PREFIX + "type:both")],
        [("❌ انصراف", PREFIX + "cancel")],
    ])


def _choose_button():
    return _kb([
        [("✅ بله، دکمه باشد", PREFIX + "button:yes")],
        [("❌ خیر، بدون دکمه", PREFIX + "button:no")],
        [("❌ انصراف", PREFIX + "cancel")],
    ])


def _destination(B):
    rows = [[("🏠 رفتن به خدمات", PREFIX + "dest:services")]]
    for r in _service_rows(B):
        rows.append([(f"🎯 {r['name']}", PREFIX + "dest:service:" + str(r['key']))])
    rows.append([("❌ انصراف", PREFIX + "cancel")])
    return _kb(rows)


def _send_keyboard(st):
    label = st.get("announce_button_label") or "🛎 استفاده از خدمات"
    dest = st.get("announce_destination")
    if not dest:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=PREFIX + "go:" + dest)]])


async def _start(update, context, B):
    q = update.callback_query
    if not q or not B.admin(q.from_user.id):
        return
    await q.answer()
    uid = q.from_user.id
    st = B.S.setdefault(uid, {"admin": True})
    action = (q.data or "").split(":", 1)[1]
    if action == "start":
        st.update({"admin_plus_mode": "announce_v2", "announce_content": None,
                   "announce_text": "", "announce_photo": None,
                   "announce_destination": None, "announce_button_label": None})
        await q.message.reply_text("📣 نوع اعلان را انتخاب کنید:", reply_markup=_choose_content())
        raise ApplicationHandlerStop
    if action == "cancel":
        for k in list(st):
            if k.startswith("announce_"):
                st.pop(k, None)
        st["admin_plus_mode"] = None
        await q.message.reply_text("❌ اعلان لغو شد.")
        raise ApplicationHandlerStop
    if action.startswith("type:"):
        kind = action.split(":", 1)[1]
        st.update({"admin_plus_mode": "announce_v2_content", "announce_content": kind,
                   "announce_text": "", "announce_photo": None})
        prompts = {
            "text": "📝 متن اعلان را ارسال کنید:",
            "photo": "🖼 عکس اعلان را ارسال کنید:",
            "both": "📝🖼 ابتدا متن اعلان را ارسال کنید؛ سپس عکس را بفرستید:",
        }
        await q.message.reply_text(prompts[kind])
        raise ApplicationHandlerStop
    if action == "button:yes":
        st["admin_plus_mode"] = "announce_v2_destination"
        await q.message.reply_text("📍 دکمه اعلان به کجا برود؟", reply_markup=_destination(B))
        raise ApplicationHandlerStop
    if action == "button:no":
        st["announce_destination"] = None
        await _deliver(update, context, B, st)
        raise ApplicationHandlerStop
    if action.startswith("dest:"):
        dest = action.split(":", 1)[1]
        st["announce_destination"] = dest
        st["admin_plus_mode"] = "announce_v2_label"
        await q.message.reply_text("✏️ متن دکمه را وارد کنید:\nمثلاً: 🛎 دریافت خدمات")
        raise ApplicationHandlerStop
    if action.startswith("go:"):
        dest = action.split(":", 1)[1]
        if dest == "services":
            await q.message.reply_text("🛎 خدمات قابل استفاده را انتخاب کنید:", reply_markup=B.main(uid))
        else:
            # Use the canonical Persian service label as the next actionable keyboard item.
            row = B.db.conn.execute("SELECT name FROM services WHERE key=? AND active=1", (dest,)).fetchone()
            if not row:
                await q.message.reply_text("❌ خدمت موردنظر دیگر فعال نیست.")
            else:
                await q.message.reply_text("🎯 خدمت انتخاب‌شده:\n" + str(row["name"]), reply_markup=B.main(uid))
        raise ApplicationHandlerStop


async def _content(update, context, B):
    msg = update.effective_message
    uid = update.effective_user.id if update.effective_user else None
    if not msg or not uid or not B.admin(uid):
        return
    st = B.S.setdefault(uid, {"admin": True})
    mode = st.get("admin_plus_mode")
    if mode not in {"announce_v2_content", "announce_v2_label"}:
        return
    if mode == "announce_v2_label":
        label = (msg.text or "").strip()
        if not label or len(label) > 64:
            await msg.reply_text("❌ متن دکمه معتبر نیست. حداکثر ۶۴ کاراکتر وارد کنید.")
            raise ApplicationHandlerStop
        st["announce_button_label"] = label
        await _deliver(update, context, B, st)
        raise ApplicationHandlerStop
    kind = st.get("announce_content")
    if kind in {"text", "both"} and not st.get("announce_text"):
        if not (msg.text or "").strip():
            await msg.reply_text("❌ متن اعلان دریافت نشد. دوباره ارسال کنید.")
            raise ApplicationHandlerStop
        st["announce_text"] = msg.text.strip()
        if kind == "both":
            await msg.reply_text("🖼 حالا عکس اعلان را ارسال کنید:")
            raise ApplicationHandlerStop
    if kind == "text":
        st["admin_plus_mode"] = "announce_v2_button"
        await msg.reply_text("آیا می‌خواهید زیر اعلان دکمه‌ای باشد؟", reply_markup=_choose_button())
        raise ApplicationHandlerStop
    if kind == "photo":
        if not msg.photo:
            await msg.reply_text("❌ عکس دریافت نشد. دوباره ارسال کنید.")
            raise ApplicationHandlerStop
        st["announce_photo"] = msg.photo[-1].file_id
        st["admin_plus_mode"] = "announce_v2_button"
        await msg.reply_text("آیا می‌خواهید زیر اعلان دکمه‌ای باشد؟", reply_markup=_choose_button())
        raise ApplicationHandlerStop
    if kind == "both" and msg.photo:
        st["announce_photo"] = msg.photo[-1].file_id
        st["admin_plus_mode"] = "announce_v2_button"
        await msg.reply_text("آیا می‌خواهید زیر اعلان دکمه‌ای باشد؟", reply_markup=_choose_button())
        raise ApplicationHandlerStop


async def _deliver(update, context, B, st):
    users = _users(B)
    ok = fail = 0
    markup = _send_keyboard(st)
    for row in users:
        try:
            chat_id = int(row["external_id"])
            photo = st.get("announce_photo")
            text = st.get("announce_text") or ""
            if photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text or None, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            ok += 1
        except Exception:
            fail += 1
    uid = update.effective_user.id
    st["admin_plus_mode"] = None
    for k in list(st):
        if k.startswith("announce_"):
            st.pop(k, None)
    await update.effective_message.reply_text(f"📣 اعلان ارسال شد.\n\n✅ موفق: {ok}\n❌ ناموفق: {fail}")


def install(app, B):
    if getattr(B, "_announcement_flow_v2", False):
        return
    async def admin_announce_entry(update, context):
        q = update.callback_query
        if not q or q.data != "adm:announce" or not B.admin(q.from_user.id):
            return
        st = B.S.setdefault(q.from_user.id, {"admin": True})
        st.update({"admin_plus_mode": "announce_v2", "announce_content": None,
                   "announce_text": "", "announce_photo": None,
                   "announce_destination": None, "announce_button_label": None})
        await q.answer()
        await q.message.reply_text("📣 نوع اعلان را انتخاب کنید:", reply_markup=_choose_content())
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(admin_announce_entry, pattern=r"^adm:announce$"), group=-100000)
    app.add_handler(CallbackQueryHandler(lambda u,c: _start(u,c,B), pattern=r"^ann2:"), group=-99999)
    app.add_handler(MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), lambda u,c: _content(u,c,B),), group=-99998)
    B._announcement_flow_v2 = True
