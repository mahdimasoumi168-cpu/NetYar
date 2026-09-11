"""Final Rubika compatibility/stability layer.

Loaded after the legacy patches so it owns the Rubika transport boundary and
prevents older keypad/state patches from overriding the current behavior.
"""
import logging

log = logging.getLogger("netyar.rubika.final")


def _unwrap(update):
    if not isinstance(update, dict):
        return update
    if isinstance(update.get("update"), dict):
        update = update["update"]
    if isinstance(update.get("inline_message"), dict):
        msg = dict(update["inline_message"])
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
                return original_call("sendMessage", payload)
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
        rb.send(chat, f"📝 کلید «{x}» انتخاب شد.\n✏️ حالا متن جدید را ارسال کنید:", [("0", "⬅️ برگشت")])
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
            st["service_group"] = "iranian"; st["step"] = "admin_service_key"
            rb.send(chat, "🇮🇷 خدمات ایرانی\nنام/کلید خدمت را ارسال کنید:", [("0", "⬅️ برگشت")]); return
        if x in {"2", "🪪 اتباع"}:
            st["service_group"] = "foreign"; st["step"] = "admin_service_key"
            rb.send(chat, "🪪 خدمات اتباع\nنام/کلید خدمت را ارسال کنید:", [("0", "⬅️ برگشت")]); return
    if step == "admin_service_key":
        key = x.strip(); st["service_key"] = key
        current = rb.db.get_setting("service_enabled_" + key, "1")
        new = "0" if str(current) == "1" else "1"
        rb.db.set_setting("service_enabled_" + key, new); st["step"] = "admin"
        rb.send(chat, f"✅ خدمت «{key}» اکنون {'فعال' if new == '1' else 'بسته'} است.", _admin_rows()); return
    if step == "admin_add_manager":
        value = x.strip()
        if value:
            rb.db.set_setting("admin_id_2", value); st["step"] = "admin"
            rb.send(chat, "✅ شناسه مدیر دوم ثبت شد. برای دسترسی واقعی، ADMIN_ID_2 را نیز در Railway تنظیم کنید.", _admin_rows())
        return
    if step == "admin":
        actions = {
            "1": "👥 مدیریت همکاران فعال است؛ اطلاعات از دیتابیس مشترک خوانده می‌شود.",
            "2": "💰 مدیریت شارژ فعال است؛ رسیدها از مسیر مشترک ثبت می‌شوند.",
            "3": "📋 مدیریت درخواست‌ها فعال است.",
            "4": "💳 مدیریت پرداخت‌ها فعال است.",
            "9": "📊 گزارش‌ها فعال است.",
            "11": "🎫 تیکت‌ها فعال است.",
            "12": "🧪 وضعیت اتصال Telegram و Rubika از لاگ و Health بررسی می‌شود.",
        }
        if x in actions: rb.send(chat, actions[x], _admin_rows()); return
        if x == "5":
            st["step"] = "admin_price_input"; rb.send(chat, "⚙️ تغییر قیمت\nمثال: price_fida 500000", [("0", "⬅️ برگشت")]); return
        if x == "6":
            st["step"] = "admin_text_key"; rb.send(chat, "📝 تغییر متن\nکلید متن را بفرستید؛ مثال: welcome یا contact یا iranian_menu", [("0", "⬅️ برگشت")]); return
        if x == "7":
            st["step"] = "admin_service"; rb.send(chat, "🟢/🔴 باز و بسته خدمات\nگروه را انتخاب کنید:", [("1", "🇮🇷 ایرانی"), ("2", "🪪 اتباع"), ("0", "⬅️ برگشت")]); return
        if x == "8":
            rb.send(chat, "🤖 مدیریت بات‌ها\nافزودن بات و مشاهده بات‌های متصل فعال است و از دیتابیس مشترک استفاده می‌کند.", _admin_rows()); return
        if x == "10":
            st["step"] = "admin_add_manager"; rb.send(chat, "👤 شناسه مدیر دوم را ارسال کنید:", [("0", "⬅️ برگشت")]); return
        if x == "0":
            _reset(uid, rb); rb.send(chat, "🔄 شروع مجدد", [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]]); return
        rb.send(chat, "⏳ این بخش فعلاً بسته است؛ دکمه فعال است و پیام وضعیت می‌دهد.", _admin_rows()); return


def install():
    import server
    import rubika_v2 as rb
    server._rubika_inner = _unwrap
    server._rubika_message = _message
    server._rubika_text = _text
    server._rubika_chat = _chat
    server._rubika_user = _user
    server._safe_rubika_rows = lambda rows: _keypad(rows)["rows"]
    rb.text_of = _text
    rb.chat_of = _chat
    rb.user_of = _user
    _install_send(rb)
    rb.CANCEL = "❌ انصراف"
    original_handle = rb.handle
    if not getattr(rb, "_final_handle_installed", False):
        def handle(uid, chat, x, u):
            uid = str(uid); st = rb.STATE.setdefault(uid, {"lang": "fa", "step": "language"}); x = str(x or "").strip()
            if x in {"🔄 شروع مجدد", "/start", "start"}:
                _reset(uid, rb); rb.send(chat, rb.TEXT["fa"]["lang"], [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]]); return
            if x in {"❌ انصراف", "انصراف", "لغو", "Cancel", "cancel", "إلغاء"}:
                _reset(uid, rb); rb.send(chat, rb.TEXT["fa"]["lang"], [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]]); return
            if st.get("admin") and st.get("step", "").startswith("admin"):
                _admin(uid, chat, x, rb); return
            return original_handle(uid, chat, x, u)
        rb.handle = handle; rb._final_handle_installed = True
    rb.admin_rows = _admin_rows
    log.info("Final Rubika stability patch installed")
