"""Continuous free-form Rubika partner <-> admin chat.

Uses Rubika's official bot API sendMessage/forwardMessage model: text is sent as
text, while media is forwarded by message id so photos/videos/voice/files do
not need a second upload step. Neither side is forced to attach media.
"""
import logging

log = logging.getLogger("netyar.rubika.ticket_chat")


def _inner(update):
    if isinstance(update, dict) and isinstance(update.get("update"), dict):
        return update["update"]
    return update if isinstance(update, dict) else {}


def _message(update):
    u = _inner(update)
    m = u.get("message") or u.get("new_message") or u.get("inline_message") or u
    return m if isinstance(m, dict) else {}


def _message_id(update):
    m = _message(update)
    for source in (m, _inner(update)):
        if isinstance(source, dict):
            value = source.get("message_id")
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""


def _chat(update):
    u = _inner(update)
    m = _message(u)
    for source in (u, m):
        if isinstance(source, dict):
            for key in ("chat_id", "chat_key", "object_guid"):
                value = source.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
    return ""


def _has_media(update):
    m = _message(update)
    if m.get("file") or m.get("file_id"):
        return True
    for key in ("photo", "video", "voice", "audio", "document", "file_inline"):
        if m.get(key):
            return True
    return False


def _forward(rb, source_chat, message_id, target_chat):
    if not source_chat or not message_id or not target_chat:
        return False
    rb.call("forwardMessage", {
        "from_chat_id": str(source_chat),
        "message_id": str(message_id),
        "to_chat_id": str(target_chat),
        "disable_notification": False,
    })
    return True


def _send_text(rb, chat, text):
    if text and str(text).strip():
        rb.send(chat, str(text).strip())
        return True
    return False


def install():
    import rubika_v2 as R
    if getattr(R, "_netyar_ticket_chat_installed", False):
        return

    old_admin = R.admin
    old_handle = R.handle

    def admin(uid, chat, x):
        uid = str(uid)
        x = str(x).strip()
        st = R.STATE.setdefault(uid, {})
        step = st.get("step")

        # Admin panel -> ticket list. The partner id is encoded in the button id,
        # so the admin never has to type a partner phone manually.
        if step == "admin" and x == "12":
            rows = []
            partners = R.db.conn.execute(
                "SELECT id,name,phone,active FROM partners ORDER BY id DESC LIMIT 50"
            ).fetchall()
            for p in partners:
                if int(p["active"] or 0):
                    rows.append([(f"ticket_partner:{p['id']}", f"💬 {p['name'] or p['phone']}")])
            rows.append([("15", "🔄 شروع مجدد")])
            R.send(
                chat,
                "🎫 مدیریت تیکت‌ها\n\nهمکار موردنظر را انتخاب کنید.\nبعد از انتخاب، هر متن، عکس، ویدیو، ویس یا فایل که بفرستید مستقیماً برای همان همکار ارسال می‌شود.",
                rows or [[("15", "🔄 شروع مجدد")]],
            )
            return

        if step == "admin" and x.startswith("ticket_partner:") and R.is_admin(uid):
            try:
                pid = int(x.split(":", 1)[1])
                p = R.db.conn.execute(
                    "SELECT id,name,phone FROM partners WHERE id=? AND active=1", (pid,)
                ).fetchone()
            except Exception:
                p = None
            if not p:
                R.send(chat, "❌ همکار پیدا نشد.", R.admin_rows())
                return
            partner_chat = R.db.setting(f"partner_chat_{p['phone']}", "")
            if not partner_chat:
                R.send(chat, "❌ این همکار هنوز در روبیکا وارد پنل نشده است؛ ابتدا همکار یک‌بار وارد پنل همکاران شود.", R.admin_rows())
                return
            st["step"] = "admin_ticket_chat"
            st["ticket_partner_id"] = int(p["id"])
            st["ticket_partner_phone"] = str(p["phone"])
            st["ticket_partner_chat"] = str(partner_chat)
            st["ticket_admin_chat"] = str(chat)
            R.db.set_setting(f"ticket_admin_{p['phone']}", str(chat))
            R.send(chat, f"💬 گفت‌وگوی مستقیم با همکار {p['name'] or p['phone']} فعال شد.\n\nهر تعداد پیام خواستید بفرستید؛ متن، عکس، ویدیو، ویس یا فایل. هیچ‌کدام اجباری نیست.\n\nبرای خروج: 🔄 شروع مجدد")
            return

        if step == "admin_ticket_chat" and R.is_admin(uid):
            target = st.get("ticket_partner_chat")
            if not target:
                st["step"] = "admin"
                R.send(chat, "❌ ارتباط با همکار پیدا نشد.", R.admin_rows())
                return
            if x in {"15", "99", R.RESTART, "🔄 شروع مجدد"}:
                st["step"] = "admin"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.admin_rows())
                return
            try:
                if _has_media({"message": {"text": x}}):
                    pass
                _send_text(R, target, f"👔 پیام مدیریت\n\n{x}")
                R.db.set_setting(f"ticket_admin_{st.get('ticket_partner_phone')}", str(chat))
                return
            except Exception:
                log.exception("Rubika admin text ticket send failed")
                R.send(chat, "❌ ارسال پیام انجام نشد. دوباره تلاش کنید.")
                return

        return old_admin(uid, chat, x)

    def handle(uid, chat, x, update):
        uid = str(uid)
        x = str(x or "").strip()
        st = R.STATE.setdefault(uid, {})
        step = st.get("step")

        if step == "partner" and x in {"6", "✉️ تیکت به مدیریت", "🎫 ارسال تیکت به مدیریت"}:
            st["step"] = "partner_ticket_chat"
            st["ticket_partner_chat"] = str(chat)
            st["ticket_admin_chat"] = R.db.setting(f"ticket_admin_{st.get('partner')}", "") or (next(iter(R.ADMIN_IDS), ""))
            R.db.set_setting(f"partner_chat_{st.get('partner')}", str(chat))
            R.send(chat, "💬 ارتباط مستقیم با مدیریت فعال شد.\n\nهر تعداد پیام خواستید بفرستید: متن، عکس، ویدیو، ویس یا فایل. هیچ‌کدام اجباری نیست.\n\nبرای خروج: 🔄 شروع مجدد")
            return

        if step == "partner_ticket_chat":
            if x in {"0", "10", "15", "99", R.CANCEL, R.RESTART, "❌ انصراف", "🔄 شروع مجدد"}:
                st["step"] = "partner"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.partner_rows())
                return
            target = st.get("ticket_admin_chat") or R.db.setting(f"ticket_admin_{st.get('partner')}", "") or next(iter(R.ADMIN_IDS), "")
            if not target:
                R.send(chat, "❌ مدیریت برای پاسخ در دسترس نیست.")
                return
            try:
                if _has_media(update):
                    if not _forward(R, chat, _message_id(update), target):
                        _send_text(R, target, f"📨 پیام همکار\n👥 {st.get('partner', '-') }\n\n{x or 'پیام رسانه‌ای'}")
                else:
                    _send_text(R, target, f"📨 پیام همکار\n👥 {st.get('partner', '-') }\n\n{x or 'پیام بدون متن'}")
                R.db.set_setting(f"ticket_admin_{st.get('partner')}", str(target))
                R.send(chat, "✅ پیام برای مدیریت ارسال شد.\nمی‌توانید پیام بعدی را هم بفرستید.")
            except Exception:
                log.exception("Rubika partner ticket send failed")
                R.send(chat, "❌ ارسال پیام انجام نشد. دوباره تلاش کنید.")
            return

        if step == "admin_ticket_chat" and R.is_admin(uid):
            target = st.get("ticket_partner_chat")
            if x in {"15", "99", R.RESTART, "🔄 شروع مجدد"}:
                st["step"] = "admin"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.admin_rows())
                return
            try:
                if _has_media(update):
                    if not _forward(R, chat, _message_id(update), target):
                        _send_text(R, target, f"👔 پیام مدیریت\n\n{x or 'پیام رسانه‌ای'}")
                else:
                    _send_text(R, target, f"👔 پیام مدیریت\n\n{x or 'پیام بدون متن'}")
                R.db.set_setting(f"ticket_admin_{st.get('ticket_partner_phone')}", str(chat))
            except Exception:
                log.exception("Rubika admin media ticket send failed")
                R.send(chat, "❌ ارسال پیام انجام نشد. دوباره تلاش کنید.")
            return

        return old_handle(uid, chat, x, update)

    R.admin = admin
    R.handle = handle
    R._netyar_ticket_chat_installed = True
    log.info("Rubika continuous partner/admin ticket chat installed")
