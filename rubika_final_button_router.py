"""Final Rubika button router.

Rubika ChatKeypad clicks carry the real button id in aux_data.button_id.
The server must route that id according to the current state instead of
converting it to visible text first.
"""
import logging

log = logging.getLogger("netyar.rubika_final_router")


def _inner(update):
    if isinstance(update, dict) and isinstance(update.get("update"), dict): return update["update"]
    return update


def _message(update):
    u = _inner(update)
    if not isinstance(u, dict): return {}
    m = u.get("message") or u.get("new_message") or u
    return m if isinstance(m, dict) else {}


def _chat(update):
    u = _inner(update); m = _message(update)
    return str((u.get("chat_id") if isinstance(u, dict) else "") or m.get("chat_id") or m.get("chat_key") or "")


def _user(update):
    m = _message(update); sender = m.get("sender") or {}
    return str(sender.get("user_id") or m.get("sender_id") or m.get("user_id") or _chat(update))


def _button_id(update):
    m = _message(update); a = m.get("aux_data")
    if isinstance(a, str):
        try:
            import json; a = json.loads(a)
        except Exception: a = None
    if isinstance(a, dict):
        bid = a.get("button_id")
        if bid is not None and str(bid).strip(): return str(bid).strip()
    return ""


def _clean_rows(rows):
    out = []
    for row in rows or []:
        rr = []
        for item in row or []:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                bid, label = str(item[0]), str(item[1])
            else:
                bid, label = "0", str(item)
            for p in ("🔵 ", "🟦 ", "🟩 ", "🟨 "):
                if label.startswith(p): label = label[len(p):].strip()
            rr.append((bid, label))
        if rr: out.append(rr)
    return out


def _numeric_label(rb, uid, step, x):
    """Translate a Rubika button id into the label expected by legacy handlers."""
    lang = rb.STATE.get(str(uid), {}).get("lang", "fa")
    fa = {
        "language": {"1":"🇮🇷 فارسی","2":"🇬🇧 English","3":"🇸🇦 العربية"},
        "citizenship": {"1":"🪪 اتباع هستم","2":"🇮🇷 ایرانی هستم"},
        "iranian": {"1":"👥 پنل همکاران","2":"🎫 پیگیری"},
        "menu": {"1":"🪪 فیدای غیر حضوری","2":"🖨 خدمات چاپ","3":"🏛 حل مشکل ورود اتباع دولت من","4":"🎫 پیگیری","5":"📱 خدمات سیم کارت","6":"📝 آزمون غربالگری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","10":"🔄 شروع مجدد"},
        "main": {"1":"🪪 فیدای غیر حضوری","2":"🖨 خدمات چاپ","3":"🏛 حل مشکل ورود اتباع دولت من","4":"🎫 پیگیری","5":"📱 خدمات سیم کارت","6":"📝 آزمون غربالگری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","10":"🔄 شروع مجدد"},
        "partner": {"1":"➕ شارژ حساب","2":"🔎 پیگیری کد","3":"📋 سوابق","4":"💰 موجودی","5":"🏛 حل مشکل سامانه دولت من","6":"✉️ تیکت به مدیریت","10":"🔄 شروع مجدد","0":rb.CANCEL},
        "admin": {"1":"👥 همکاران","2":"💰 شارژها","3":"📋 درخواست‌ها","4":"💳 پرداخت‌های مشتری","5":"⚙️ قیمت‌ها","6":"🤖 افزودن بات","7":"🤖 بات‌های متصل","8":"📊 گزارش","10":"🔄 شروع مجدد","0":"⬅️ منوی اصلی"},
        "print_color": {"1":"⚫ سیاه و سفید","2":"🌈 رنگی","0":rb.CANCEL},
        "print_side": {"1":"📄 یک‌رو","2":"🔄 پشت‌ورو","0":rb.CANCEL},
        "print_files": {"1":"✅ تأیید","0":rb.CANCEL},
        "print": {"1":"✅ تأیید","0":rb.CANCEL},
        "topup_amount": {"0":rb.CANCEL}, "topup_receipt": {"0":rb.CANCEL},
        "track": {"0":rb.CANCEL}, "track_partner": {"0":rb.CANCEL},
        "partner_phone": {"0":rb.CANCEL}, "partner_pass": {"0":rb.CANCEL},
        "gov_fida": {"0":rb.CANCEL}, "partner_gov_fida": {"0":rb.CANCEL},
        "gov_yekta": {"0":rb.CANCEL}, "gov_dob": {"0":rb.CANCEL}, "fida_doc": {"0":rb.CANCEL},
    }
    label = fa.get(step, {}).get(str(x))
    if label: return label
    return None


def install():
    try:
        import server
        import rubika_v2 as rb
        # Critical: preserve numeric button_id through server processing.
        server._normalize_rubika_button = lambda update, _rb: update

        old_patch = getattr(server, "_patch_rubika", None)
        if old_patch and not getattr(server, "_netyar_final_router_patch", False):
            def patch(r):
                result = old_patch(r)

                def main_rows(uid):
                    lang = r.STATE.get(str(uid), {}).get("lang", "fa")
                    if lang == "en":
                        rows = [[("1", "FIDA non-in-person"), ("2", "Printing")],[("3", "Government access issue"), ("4", "Tracking")],[("5", "SIM services"), ("6", "Screening & follow-up")],[("7", "My wallet"), ("8", "Partner panel")],[("9", "Contact us"), ("10", "Start again")]]
                    elif lang == "ar":
                        rows = [[("1", "خدمة فيدا"), ("2", "الطباعة")],[("3", "مشكلة خدمات الحكومة"), ("4", "متابعة")],[("5", "خدمات الشريحة"), ("6", "الفحص والمتابعة")],[("7", "محفظتي"), ("8", "لوحة الشركاء")],[("9", "اتصل بنا"), ("10", "بدء من جديد")]]
                    else:
                        rows = [[("1", "🪪 فیدای غیر حضوری"), ("2", "🖨 خدمات چاپ")],[("3", "🏛 حل مشکل ورود اتباع دولت من"), ("4", "🎫 پیگیری")],[("5", "📱 خدمات سیم کارت"), ("6", "📝 آزمون غربالگری و پیگیری")],[("7", "💰 کیف پول من"), ("8", "👥 پنل همکاران")],[("9", "📞 تماس با ما"), ("10", "🔄 شروع مجدد")]]
                    if str(uid) in getattr(r, "ADMIN_IDS", set()): rows.append([("99", "🛠 پنل مدیریت بات")])
                    return _clean_rows(rows)

                r.main_rows = main_rows

                if not getattr(r, "_netyar_final_process_router", False):
                    old_process = r.process
                    def process(update):
                        bid = _button_id(update)
                        if bid:
                            uid = _user(update); chat = _chat(update)
                            if uid and chat:
                                return r.handle(uid, chat, bid, update)
                        return old_process(update)
                    r.process = process
                    r._netyar_final_process_router = True

                if not getattr(r, "_netyar_final_handle_router", False):
                    previous = r.handle
                    aliases = {"🔄 شروع مجدد":"10","Start again":"10","Restart":"10","بدء من جديد":"10","👥 پنل همکاران":"8","Partner panel":"8","لوحة الشركاء":"8","🎫 پیگیری":"4","Tracking":"4","المتابعة":"4","🛠 پنل مدیریت بات":r.ADMIN_COMMAND,"🛠 پنل مدیریت":r.ADMIN_COMMAND,"Admin panel":r.ADMIN_COMMAND,"لوحة الإدارة":r.ADMIN_COMMAND}
                    def handle(uid, chat, x, u):
                        text = str(x or "").strip()
                        st = r.STATE.setdefault(str(uid), {})
                        if text.isdigit():
                            mapped = _numeric_label(r, uid, st.get("step") or st.get("mode") or "", text)
                            if mapped is not None: text = mapped
                        if text == "99" and st.get("step") in {"main","menu","service"} and str(uid) in getattr(r,"ADMIN_IDS",set()): text = r.ADMIN_COMMAND
                        mapped = aliases.get(text)
                        if mapped is not None: text = mapped
                        if text == "10":
                            lang = st.get("lang", "fa")
                            citizenship = st.get("citizenship") or st.get("status")
                            r.STATE[str(uid)] = {"lang":lang}
                            if citizenship:
                                r.STATE[str(uid)]["citizenship"] = citizenship
                                r.STATE[str(uid)]["status"] = citizenship
                            r.STATE[str(uid)]["step"] = "language"
                            return r.send(chat, r.TEXT[lang]["lang"], [[("1","🇮🇷 فارسی"),("2","🇬🇧 English"),("3","🇸🇦 العربية")]])
                        return previous(uid, chat, text, u)
                    r.handle = handle
                    r._netyar_final_handle_router = True
                return result
            server._patch_rubika = patch
            server._netyar_final_router_patch = True
    except Exception:
        log.exception("Rubika final button router installation failed")
