"""Final isolated Rubika fixes.

This module touches only Rubika runtime objects. It is intentionally loaded by
rubika_bootstrap_final.py and does not register or modify Telegram handlers.
"""
import json


def install(rb=None):
    if rb is None:
        import rubika_v2 as rb
    if getattr(rb, "_netyar_final_safe_overlay_v1", False):
        return

    # 1) Correct the canonical numeric button mapping. The old server mapper
    # had the Iranian and main-menu actions swapped for several ids.
    try:
        import server
        old_normalize = getattr(server, "_normalize_rubika_button", None)
        def normalize(update, R=rb):
            # Preserve the existing normalizer for payload extraction, but use
            # the actual menu state to resolve numeric keypad ids.
            raw = ""
            try:
                raw = str(server._rubika_text(update) or "").strip()
            except Exception:
                pass
            if raw not in {str(i) for i in range(10)}:
                return old_normalize(update, R) if callable(old_normalize) else update
            uid = str(server._rubika_user(update))
            step = str(R.STATE.get(uid, {}).get("step") or "")
            maps = {
                "language": {"1":"🇮🇷 فارسی","2":"🇬🇧 English","3":"🇸🇦 العربية"},
                "citizenship": {"1":"🪪 اتباع هستم","2":"🇮🇷 ایرانی هستم"},
                "iranian": {"1":"🎫 پیگیری","2":"👥 پنل همکاران","10":R.RESTART},
                "main": {"1":"🪪 فیدای غیر حضوری","2":"🏛 حل مشکل ورود اتباع دولت من","3":"🏛 حل مشکل ورود اتباع دولت من","4":"🎫 پیگیری","5":"📝 آزمون غربالگری","6":"📝 آزمون غربالگری و پیگیری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","10":R.RESTART},
                "menu": {"1":"🪪 فیدای غیر حضوری","2":"🏛 حل مشکل ورود اتباع دولت من","3":"🏛 حل مشکل ورود اتباع دولت من","4":"🎫 پیگیری","5":"📝 آزمون غربالگری","6":"📝 آزمون غربالگری","7":"💰 کیف پول من","8":"👥 پنل همکاران","9":"📞 تماس با ما","0":R.CANCEL},
                "partner": {"1":"➕ شارژ حساب","2":"🔎 پیگیری کد","3":"📋 سوابق","4":"💰 موجودی","5":"🏛 حل مشکل سامانه دولت من","6":"✉️ تیکت به مدیریت","10":R.RESTART,"0":R.CANCEL},
                "print": {"1":"⚫ سیاه و سفید","2":"🌈 رنگی","0":R.CANCEL},
                "print_color": {"1":"⚫ سیاه و سفید","2":"🌈 رنگی","0":R.CANCEL},
                "print_side": {"1":"📄 یک‌رو","2":"🔄 پشت‌ورو","0":R.CANCEL},
                "print_files": {"1":"✅ تأیید","0":R.CANCEL},
                "topup_amount": {"0":R.CANCEL}, "topup_receipt":{"0":R.CANCEL},
                "track":{"0":R.CANCEL}, "track_partner":{"0":R.CANCEL},
                "partner_phone":{"0":R.CANCEL}, "partner_pass":{"0":R.CANCEL},
                "gov_doc":{"0":R.CANCEL}, "gov_fida":{"0":R.CANCEL},
                "partner_gov_fida":{"0":R.CANCEL}, "gov_yekta":{"0":R.CANCEL},
                "gov_dob":{"0":R.CANCEL}, "fida_doc":{"0":R.CANCEL},
            }
            label = maps.get(step, {}).get(raw)
            if not label:
                return old_normalize(update, R) if callable(old_normalize) else update
            m = server._rubika_message(update)
            if isinstance(m, dict):
                m["text"] = label
            return update
        server._normalize_rubika_button = normalize
    except Exception:
        pass

    # 2) Fix admin sub-state routing. The legacy admin() contains some
    # sub-state checks nested under step=='admin', making them unreachable.
    if not getattr(rb, "_netyar_admin_substate_fix_v1", False):
        old_admin = rb.admin
        def admin(uid, chat, x):
            uid = str(uid); x = str(x or "").strip()
            st = rb.STATE.setdefault(uid, {})
            step = st.get("step")
            if step == "admin_service":
                parts = x.split()
                if len(parts) == 2 and parts[1] in {"open","close","باز","بسته"}:
                    active = 1 if parts[1] in {"open","باز"} else 0
                    rb.db.conn.execute("UPDATE services SET active=? WHERE key=?", (active, parts[0]))
                    rb.db.conn.commit()
                    st["step"] = "admin"
                    return rb.send(chat, "✅ وضعیت خدمت تغییر کرد.", rb.admin_rows())
                return rb.send(chat, "❌ فرمت صحیح: service_key open یا service_key close", rb.admin_rows())
            if step == "admin_text_key":
                st["text_key"] = x; st["step"] = "admin_text"
                return rb.send(chat, "✏️ متن جدید را ارسال کنید:", [[("0", rb.CANCEL)]])
            if step == "admin_text":
                key = st.get("text_key")
                if not key:
                    st["step"] = "admin"
                    return rb.send(chat, "❌ کلید متن مشخص نیست.", rb.admin_rows())
                rb.db.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, x))
                rb.db.conn.commit(); st["step"] = "admin"
                return rb.send(chat, "✅ متن ذخیره شد.", rb.admin_rows())
            if step == "admin_price":
                parts = x.split()
                if len(parts) != 2 or not parts[1].isdigit():
                    return rb.send(chat, "❌ فرمت صحیح: کلید قیمت + مبلغ\nمثال: price_government 500000", [[("0", rb.CANCEL)]])
                rb.db.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (parts[0], parts[1]))
                rb.db.conn.commit(); st["step"] = "admin"
                return rb.send(chat, "✅ قیمت ذخیره شد.", rb.admin_rows())
            if step == "admin_bot_platform":
                mp = {"1":"Telegram","2":"Rubika","3":"Bale","4":"Eitaa"}
                if x not in mp:
                    return rb.send(chat, "❌ یکی از پیام‌رسان‌های نمایش‌داده‌شده را انتخاب کنید.", [[("1","Telegram"),("2","Rubika")],[ ("3","Bale"),("4","Eitaa")],[("0",rb.CANCEL)]])
                st["bot_platform"] = mp[x]; st["step"] = "admin_bot_name"
                return rb.send(chat, "🤖 نام بات را وارد کنید:", [[("0",rb.CANCEL)]])
            if step == "admin_bot_name":
                if not x: return rb.send(chat, "❌ نام بات را وارد کنید.")
                st["bot_name"] = x; st["step"] = "bot_api"
                return rb.send(chat, rb.T(uid,"bot_api"), [[("0",rb.CANCEL)]])
            return old_admin(uid, chat, x)
        rb.admin = admin
        rb._netyar_admin_substate_fix_v1 = True

    rb._netyar_final_safe_overlay_v1 = True
