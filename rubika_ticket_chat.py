"""Continuous, reliable Rubika partner <-> admin chat.

The partner identity used by rubika_v2 is the partner phone number. This module
keeps that identity consistently for persisted chat routing, while using the
actual Rubika chat id for delivery. Text and media are both supported and no
attachment is mandatory.
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


def _partner_phone(st):
    return str(st.get("partner") or st.get("ticket_partner_phone") or "").strip()


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
                "🎫 ارتباط با همکار\n\nهمکار موردنظر را انتخاب کنید.\nبعد از انتخاب، می‌توانید هر تعداد پیام متنی یا رسانه‌ای برای همان همکار ارسال کنید.",
                rows,
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

            phone = str(p["phone"] or "").strip()
            partner_chat = R.db.setting(f"partner_chat_{phone}", "").strip()
            if not partner_chat:
                # Compatibility with older records that may have been saved by id.
                partner_chat = R.db.setting(f"partner_chat_{pid}", "").strip()
            if not partner_chat:
                R.send(
                    chat,
                    "❌ چت روبیکای این همکار هنوز ثبت نشده است.\n\nاز همکار بخواهید یک‌بار وارد «پنل همکاران» شود تا ارتباط او ثبت شود.",
                    R.admin_rows(),
                )
                return

            st["step"] = "admin_ticket_chat"
            st["ticket_partner_id"] = int(p["id"])
            st["ticket_partner_phone"] = phone
            st["ticket_partner_chat"] = str(partner_chat)
            st["ticket_admin_chat"] = str(chat)
            R.db.set_setting(f"ticket_admin_{phone}", str(chat))
            R.send(
                chat,
                f"💬 ارتباط با همکار «{p['name'] or phone}» فعال شد.\n\n"
                "حالا متن، عکس، ویدیو، ویس یا فایل را بفرستید. هیچ نوع فایل اجباری نیست.\n\n"
                "برای خروج: 🔄 شروع مجدد"
            )
            return

        if step == "admin_ticket_chat" and R.is_admin(uid):
            target = str(st.get("ticket_partner_chat") or "").strip()
            if not target:
                st["step"] = "admin"
                R.send(chat, "❌ ارتباط با همکار پیدا نشد.", R.admin_rows())
                return
            if x in {"15", "99", R.RESTART, "🔄 شروع مجدد"}:
                st["step"] = "admin"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.admin_rows())
                return
            try:
                _send_text(R, target, f"👔 پیام مدیریت\n\n{x}")
                R.db.set_setting(f"ticket_admin_{_partner_phone(st)}", str(chat))
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
            phone = _partner_phone(st)
            st["step"] = "partner_ticket_chat"
            st["ticket_partner_chat"] = str(chat)
            st["ticket_partner_phone"] = phone
            st["ticket_admin_chat"] = R.db.setting(f"ticket_admin_{phone}", "") or next(iter(R.ADMIN_IDS), "")
            R.db.set_setting(f"partner_chat_{phone}", str(chat))
            R.send(
                chat,
                "💬 ارتباط مستقیم با مدیریت فعال شد.\n\n"
                "هر تعداد پیام خواستید بفرستید: متن، عکس، ویدیو، ویس یا فایل.\n"
                "هیچ‌کدام اجباری نیست.\n\n"
                "برای خروج: 🔄 شروع مجدد"
            )
            return

        if step == "partner_ticket_chat":
            if x in {"0", "10", "15", "99", R.CANCEL, R.RESTART, "❌ انصراف", "🔄 شروع مجدد"}:
                st["step"] = "partner"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.partner_rows())
                return

            phone = _partner_phone(st)
            target = str(st.get("ticket_admin_chat") or R.db.setting(f"ticket_admin_{phone}", "") or next(iter(R.ADMIN_IDS), "")).strip()
            if not target:
                R.send(chat, "❌ مدیریت برای پاسخ در دسترس نیست.")
                return
            try:
                if _has_media(update):
                    if not _forward(R, chat, _message_id(update), target):
                        _send_text(R, target, f"📨 پیام همکار\n👥 {phone or '-'}\n\n{x or 'پیام رسانه‌ای'}")
                else:
                    _send_text(R, target, f"📨 پیام همکار\n👥 {phone or '-'}\n\n{x or 'پیام بدون متن'}")
                R.db.set_setting(f"ticket_admin_{phone}", str(target))
                R.send(chat, "✅ پیام برای مدیریت ارسال شد.\nمی‌توانید پیام بعدی را هم بفرستید.")
            except Exception:
                log.exception("Rubika partner ticket send failed")
                R.send(chat, "❌ ارسال پیام انجام نشد. دوباره تلاش کنید.")
            return

        if step == "admin_ticket_chat" and R.is_admin(uid):
            target = str(st.get("ticket_partner_chat") or "").strip()
            if x in {"15", "99", R.RESTART, "🔄 شروع مجدد"}:
                st["step"] = "admin"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.admin_rows())
                return
            if not target:
                R.send(chat, "❌ چت همکار پیدا نشد.", R.admin_rows())
                st["step"] = "admin"
                return
            try:
                if _has_media(update):
                    if not _forward(R, chat, _message_id(update), target):
                        _send_text(R, target, f"👔 پیام مدیریت\n\n{x or 'پیام رسانه‌ای'}")
                else:
                    _send_text(R, target, f"👔 پیام مدیریت\n\n{x or 'پیام بدون متن'}")
                R.db.set_setting(f"ticket_admin_{_partner_phone(st)}", str(chat))
            except Exception:
                log.exception("Rubika admin media ticket send failed")
                R.send(chat, "❌ ارسال پیام انجام نشد. دوباره تلاش کنید.")
            return

        return old_handle(uid, chat, x, update)

    R.admin = admin
    R.handle = handle
    R._netyar_ticket_chat_installed = True
    log.info("Rubika continuous partner/admin ticket chat installed")
