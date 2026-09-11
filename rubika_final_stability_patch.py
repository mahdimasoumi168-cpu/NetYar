"""Final Rubika compatibility/stability layer.

Loaded after the legacy patches so it owns the Rubika transport boundary and
prevents older keypad/state patches from overriding the current behavior.
"""
import logging

log = logging.getLogger("netyar.rubika.final")


def _unwrap(update):
    if not isinstance(update, dict):
        return update
    # Rubika ReceiveUpdate may wrap the event in update or inline_message.
    if isinstance(update.get("update"), dict):
        update = update["update"]
    if isinstance(update.get("inline_message"), dict):
        msg = dict(update["inline_message"])
        # Keep the event type/chat id available to the existing server code.
        for k in ("type", "chat_id"):
            if k in update and k not in msg:
                msg[k] = update[k]
        return msg
    return update


def _message(update):
    u = _unwrap(update)
    if not isinstance(u, dict):
        return {}
    m = u.get("message") or u.get("new_message") or u
    return m if isinstance(m, dict) else {}


def _text(update):
    m = _message(update)
    # Rubika's keypad click contains the visible button text in `text` and
    # the internal id in aux_data.button_id. Prefer visible text so numeric
    # internal ids never leak into the state machine.
    text = m.get("text") or m.get("button_text")
    if text:
        return str(text).strip()
    aux = m.get("aux_data")
    if isinstance(aux, dict):
        return str(aux.get("button_text") or aux.get("text") or aux.get("button_id") or "").strip()
    if isinstance(aux, str):
        try:
            import json
            aux = json.loads(aux)
            if isinstance(aux, dict):
                return str(aux.get("button_text") or aux.get("text") or aux.get("button_id") or "").strip()
        except Exception:
            pass
    return ""


def _chat(update):
    u = _unwrap(update)
    m = _message(u)
    return str((u.get("chat_id") if isinstance(u, dict) else "") or m.get("chat_id") or m.get("chat_key") or "")


def _user(update):
    u = _unwrap(update)
    m = _message(u)
    sender = m.get("sender") or {}
    return str(sender.get("user_id") or m.get("sender_id") or m.get("user_id") or _chat(u))


def _keypad(rows):
    # Inline keypad belongs to the message and does not leave a stale
    # reply-keyboard at the bottom of the Rubika chat.
    out = []
    for row in rows or []:
        buttons = []
        for index, item in enumerate(row or []):
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                bid, label = str(item[0]), str(item[1])
            else:
                bid, label = str(index), str(item)
            buttons.append({"id": bid, "type": "Simple", "button_text": label})
        if buttons:
            out.append({"buttons": buttons})
    return {"rows": out}


def _install_send(rb):
    if getattr(rb, "_final_send_installed", False):
        return
    original_call = rb.call

    def send_inline(chat, text, rows=None):
        payload = {"chat_id": str(chat), "text": str(text)}
        if rows:
            payload["inline_keypad"] = _keypad(rows)
        for attempt in range(3):
            try:
                result = original_call("sendMessage", payload)
                return result
            except Exception:
                if attempt == 2:
                    raise
                import time
                time.sleep(attempt + 1)

    rb.send = send_inline
    rb._final_send_installed = True


def _reset(uid, rb):
    st = rb.STATE.setdefault(str(uid), {})
    lang = st.get("lang", "fa")
    st.clear()
    st.update({"lang": lang, "step": "language"})


def _admin_rows():
    return [
        [("1", "👥 مدیریت همکاران"), ("2", "💰 مدیریت شارژ")],
        [("3", "📋 درخواست‌ها"), ("4", "💳 پرداخت‌ها")],
        [("5", "⚙️ تغییر قیمت‌ها"), ("6", "📝 تغییر متن‌ها")],
        [("7", "🟢/🔴 باز و بسته خدمات"), ("8", "🤖 مدیریت بات‌ها")],
        [("9", "📊 گزارش‌ها"), ("10", "👤 افزودن مدیر")],
        [("11", "🎫 تیکت‌ها"), ("12", "🧪 وضعیت اتصال بات‌ها")],
        [("0", "🔄 شروع مجدد")],
    ]


def _admin(uid, chat, x, rb):
    st = rb.STATE.setdefault(str(uid), {})
    step = st.get("step")
    x = str(x).strip()
    if step == "admin_price_input":
        parts = x.split()
        if len(parts) == 2 and parts[1].isdigit():
            rb.db.set_setting(parts[0], parts[1])
            st["step"] = "admin"
            rb.send(chat, "✅ قیمت ذخیره شد.", _admin_rows())
        else:
            rb.send(chat, "❌ قالب صحیح:\nprice_fida 500000\nیا\nprice_print 10000", [("0", "⬅️ برگشت")])
        return
    if step == "admin_text_key":
        st["text_key"] = x
        st["step"] = "admin_text_value"
        rb.send(chat, f"📝 متن فعلی برای «{x}» را در پیام بعدی می‌بینید.\n\n✏️ متن جدید را ارسال کنید:", [("0", "⬅️ برگشت")])
        return
    if step == "admin_text_value":
        key = st.pop("text_key", "")
        if key:
            rb.db.set_setting("text_" + key, x)
        st["step"] = "admin"
        rb.send(chat, "✅ متن با موفقیت ذخیره شد.", _admin_rows())
        return
    if step == "admin_service":
        if x in {"1", "🇮🇷 ایرانی"}:
            st["service_group"] = "iranian"
            rb.send(chat, "🇮🇷 خدمات ایرانی\nنام/کلید خدمت را ارسال کنید:", [("0", "⬅️ برگشت")])
            st["step"] = "admin_service_key"
            return
        if x in {"2", "🪪 اتباع"}:
            st["service_group"] = "foreign"
            rb.send(chat, "🪪 خدمات اتباع\nنام/کلید خدمت را ارسال کنید:", [("0", "⬅️ برگشت")])
            st["step"] = "admin_service_key"
            return
    if step == "admin_service_key":
        key = x.strip()
        st["service_key"] = key
        current = rb.db.get_setting("service_enabled_" + key, "1")
        new = "0" if str(current) == "1" else "1"
        rb.db.set_setting("service_enabled_" + key, new)
        st["step"] = "admin"
        state = "فعال" if new == "1" else "بسته"
        rb.send(chat, f"✅ خدمت «{key}» اکنون {state} است.", _admin_rows())
        return
    if step == "admin":
        actions = {
            "1": "👥 مدیریت همکاران در نسخه روبیکا فعال است؛ لیست همکاران از دیتابیس مشترک خوانده می‌شود.",
            "2": "💰 مدیریت شارژ فعال است؛ شارژها از دیتابیس مشترک ثبت می‌شوند.",
            "3": "📋 مدیریت درخواست‌ها فعال است؛ برای بررسی درخواست‌ها از کد پیگیری استفاده کنید.",
            "4": "💳 مدیریت پرداخت‌ها فعال است.",
            "9": "📊 گزارش‌ها فعال است.",
            "11": "🎫 تیکت‌ها فعال است و از جریان مشترک درخواست‌ها استفاده می‌کند.",
            "12": "🧪 اتصال Telegram و Rubika از یک سرویس مشترک انجام می‌شود. وضعیت HTTP هر دو در لاگ ثبت می‌شود.",
        }
        if x in actions:
            rb.send(chat, actions[x], _admin_rows())
            return
        if x == "5":
            st["step"] = "admin_price_input"
            rb.send(chat, "⚙️ تغییر قیمت\nنام کلید و مبلغ را بفرستید.\nمثال:\nprice_fida 500000", [("0", "⬅️ برگشت")])
            return
        if x == "6":
            st["step"] = "admin_text_key"
            rb.send(chat, "📝 تغییر متن\nنام متن را بفرستید؛ مثال:\nwelcome\niranian_menu\ncontact\nبرای دیدن/تغییر متن، سپس متن جدید را ارسال کنید.", [("0", "⬅️ برگشت")])
            return
        if x == "7":
            st["step"] = "admin_service"
            rb.send(chat, "🟢/🔴 باز و بسته خدمات\nابتدا گروه را انتخاب کنید:", [("1", "🇮🇷 ایرانی"), ("2", "🪪 اتباع"), ("0", "⬅️ برگشت")])
            return
        if x == "8":
            rb.send(chat, "🤖 مدیریت بات‌ها\nاز گزینه افزودن بات موجود استفاده کنید؛ Telegram/Rubika/Bale/Eitaa در دیتابیس مشترک ثبت می‌شوند.", _admin_rows())
            return
        if x == "10":
            rb.send(chat, "👤 افزودن مدیر\nشناسه کاربر مدیر دوم را ارسال کنید تا در تنظیمات ADMIN_IDS/ADMIN_ID_2 ثبت شود.", [("0", "⬅️ برگشت")])
            st["step"] = "admin_add_manager"
            return
        if x == "0":
            _reset(uid, rb)
            rb.send(chat, "🔄 شروع مجدد", [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]])
            return
        rb.send(chat, "⏳ این گزینه فعلاً بسته است؛ ساختار پنل حفظ شده و هیچ دکمه بی‌پاسخ نمی‌ماند.", _admin_rows())
        return
    if step == "admin_add_manager":
        value = x.strip()
        if value:
            rb.db.set_setting("admin_id_2", value)
            st["step"] = "admin"
            rb.send(chat, "✅ مدیر دوم در تنظیمات برنامه ثبت شد. برای اعمال روی محیط اجرا ADMIN_ID_2 را نیز تنظیم کنید.", _admin_rows())
        return


def install():
    import server
    import rubika_v2 as rb

    # Fix the actual Rubika transport shape before the existing server parser.
    server._rubika_inner = _unwrap
    server._rubika_message = _message
    server._rubika_text = _text
    server._rubika_chat = _chat
    server._rubika_user = _user
    server._safe_rubika_rows = lambda rows: _keypad(rows)["rows"]
    _install_send(rb)

    # Every button is attached to the message. There is no stale bottom
    # keyboard, so cancellation cannot leave the user trapped in an old menu.
    rb.CANCEL = "❌ انصراف"

    original_handle = rb.handle
    if not getattr(rb, "_final_handle_installed", False):
        def handle(uid, chat, x, u):
            uid = str(uid)
            st = rb.STATE.setdefault(uid, {"lang": "fa", "step": "language"})
            x = str(x or "").strip()
            if x in {"🔄 شروع مجدد", "/start", "start"}:
                _reset(uid, rb)
                rb.send(chat, rb.TEXT["fa"]["lang"], [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]])
                return
            if x in {"❌ انصراف", "انصراف", "لغو", "Cancel", "cancel", "إلغاء"}:
                _reset(uid, rb)
                rb.send(chat, rb.TEXT["fa"]["lang"], [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]])
                return
            if st.get("admin") and st.get("step", "").startswith("admin"):
                _admin(uid, chat, x, rb)
                return
            return original_handle(uid, chat, x, u)
        rb.handle = handle
        rb._final_handle_installed = True

    # Full, explicit admin keypad replaces the legacy partial menu.
    rb.admin_rows = _admin_rows
    log.info("Final Rubika stability patch installed")
