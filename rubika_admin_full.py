"""Full, deterministic Rubika admin menu backed by the shared SQLite DB.

The Telegram admin controller cannot operate the Rubika conversation state by
itself. This layer gives Rubika its own complete admin navigation while using
the same database, so service status/prices/settings remain cross-platform.
"""
import logging
log = logging.getLogger("netyar.rubika.admin_full")


def _fa_num(v):
    return str(v).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _menu(rb):
    return [
        [("1", "👥 مدیریت همکاران"), ("2", "💰 شارژها")],
        [("3", "📋 درخواست‌ها"), ("4", "💳 پرداخت‌ها")],
        [("5", "💰 قیمت خدمات"), ("6", "🤖 مدیریت بات‌ها")],
        [("7", "📡 بات‌های متصل"), ("8", "📊 گزارش‌ها")],
        [("9", "🛠 باز/بسته خدمات"), ("10", "📝 تغییر متن‌ها")],
        [("11", "🔐 مدیریت مدیران"), ("12", "🔄 شروع مجدد")],
        [("0", "⬅️ منوی اصلی")],
    ]


def _services(rb):
    rows = []
    for r in rb.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall():
        state = "🟢 باز" if int(r["active"] or 0) else "🔴 بسته"
        rows.append([(str(r["key"]), f"{state} {r['name']}")])
    rows.append([("0", "⬅️ بازگشت")])
    return rows


def _texts():
    return [
        [("1", "خوش‌آمدگویی فارسی"), ("2", "پیام پشتیبانی")],
        [("3", "پیام تماس با ما"), ("4", "پیام خدمات ایرانی")],
        [("5", "پیام خدمات اتباع")],
        [("0", "⬅️ بازگشت")],
    ]


def install():
    import rubika_v2 as rb
    if getattr(rb, "_netyar_rubika_admin_full", False):
        return

    old_rows = rb.admin_rows
    old_handle = rb.handle

    def admin_rows():
        return _menu(rb)
    rb.admin_rows = admin_rows

    def save_text(uid, key, value):
        rb.db.set_setting("rubika_text_" + key, value)
        # Keep the current process immediately in sync as well.
        if key == "welcome_fa":
            rb.TEXT["fa"]["menu"] = value
        elif key == "support":
            rb.TEXT["fa"]["bad"] = value
        elif key == "contact":
            rb.TEXT["fa"]["menu"] = rb.TEXT["fa"].get("menu", "")
        elif key == "iran":
            rb.TEXT["fa"]["iran"] = value

    def text_value(key):
        defaults = {
            "welcome_fa": rb.TEXT["fa"].get("menu", ""),
            "support": rb.TEXT["fa"].get("bad", ""),
            "contact": "📞 برای پشتیبانی با @Good_ok_2000 در تماس باشید.",
            "iran": rb.TEXT["fa"].get("iran", ""),
            "foreign": rb.TEXT["fa"].get("menu", ""),
        }
        return rb.db.setting("rubika_text_" + key, defaults[key])

    def admin_action(uid, chat, t):
        st = rb.STATE.setdefault(str(uid), {})
        mode = st.get("rubika_admin_mode")

        if mode == "service_select":
            if t == "0":
                st.pop("rubika_admin_mode", None)
                return rb.send(chat, rb.T(uid, "admin"), _menu(rb))
            row = rb.db.conn.execute("SELECT * FROM services WHERE key=?", (str(t),)).fetchone()
            if not row:
                return rb.send(chat, "❌ این خدمت پیدا نشد.", _services(rb))
            st["rubika_service_key"] = str(row["key"])
            st["rubika_admin_mode"] = "service_action"
            return rb.send(chat, f"🛠 {row['name']}\n💰 {int(row['price'] or 0):,} تومان\n📌 وضعیت: {'باز' if row['active'] else 'بسته'}", [[("1", "🔄 تغییر وضعیت")],[('2','✏️ تغییر نام')],[('3','💰 تغییر قیمت')],[('0','⬅️ بازگشت')]])

        if mode == "service_action":
            key = st.get("rubika_service_key")
            if t == "0":
                st["rubika_admin_mode"] = "service_select"
                return rb.send(chat, "🛠 باز/بسته خدمات", _services(rb))
            if not key:
                st.pop("rubika_admin_mode", None)
                return rb.send(chat, rb.T(uid, "admin"), _menu(rb))
            if t == "1":
                r = rb.db.conn.execute("SELECT active FROM services WHERE key=?", (key,)).fetchone()
                if r:
                    new = 0 if int(r["active"] or 0) else 1
                    rb.db.conn.execute("UPDATE services SET active=? WHERE key=?", (new, key)); rb.db.conn.commit()
                    st["rubika_admin_mode"] = "service_select"
                    return rb.send(chat, "🟢 خدمت باز شد." if new else "🔴 خدمت بسته شد.", _services(rb))
            if t == "2":
                st["rubika_admin_mode"] = "service_name"
                return rb.send(chat, "✏️ نام جدید خدمت را ارسال کنید.", [[("0", "⬅️ انصراف")]])
            if t == "3":
                st["rubika_admin_mode"] = "service_price"
                return rb.send(chat, "💰 قیمت جدید را فقط به تومان و به صورت عدد ارسال کنید.", [[("0", "⬅️ انصراف")]])

        if mode in ("service_name", "service_price"):
            if t == "0":
                st["rubika_admin_mode"] = "service_select"
                return rb.send(chat, "🛠 باز/بسته خدمات", _services(rb))
            key = st.get("rubika_service_key")
            if not key:
                st.pop("rubika_admin_mode", None)
                return rb.send(chat, rb.T(uid, "admin"), _menu(rb))
            if mode == "service_name":
                rb.db.conn.execute("UPDATE services SET name=? WHERE key=?", (str(t).strip(), key)); rb.db.conn.commit()
                st["rubika_admin_mode"] = "service_select"
                return rb.send(chat, "✅ نام خدمت تغییر کرد.", _services(rb))
            raw = str(t).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace(",", "").replace("٬", "").replace(" ", "")
            if not raw.isdigit():
                return rb.send(chat, "❌ قیمت باید عدد باشد.", [[("0", "⬅️ انصراف")]])
            amount = int(raw)
            rb.db.conn.execute("UPDATE services SET price=? WHERE key=?", (amount, key)); rb.db.set_setting("price_" + key, amount)
            rb.db.conn.commit()
            st["rubika_admin_mode"] = "service_select"
            return rb.send(chat, f"✅ قیمت به {amount:,} تومان تغییر کرد.", _services(rb))

        if mode == "text_select":
            keys = {"1":"welcome_fa","2":"support","3":"contact","4":"iran","5":"foreign"}
            if t == "0":
                st.pop("rubika_admin_mode", None); return rb.send(chat, rb.T(uid, "admin"), _menu(rb))
            key = keys.get(str(t))
            if not key: return rb.send(chat, "❌ گزینه نامعتبر است.", _texts())
            st["rubika_text_key"] = key; st["rubika_admin_mode"] = "text_value"
            return rb.send(chat, "📝 متن فعلی:\n\n" + text_value(key) + "\n\n✏️ متن جدید را ارسال کنید:", [[("0", "⬅️ انصراف")]])

        if mode == "text_value":
            if t == "0":
                st["rubika_admin_mode"] = "text_select"; return rb.send(chat, "📝 تغییر متن‌ها", _texts())
            key = st.get("rubika_text_key")
            if key:
                save_text(uid, key, str(t))
            st["rubika_admin_mode"] = "text_select"
            return rb.send(chat, "✅ متن با موفقیت ذخیره شد.", _texts())

        if mode == "admin_add":
            if t == "0":
                st.pop("rubika_admin_mode", None); return rb.send(chat, rb.T(uid, "admin"), _menu(rb))
            platform = st.get("rubika_admin_platform", "rubika")
            rb.db.conn.execute("INSERT OR REPLACE INTO admins(platform,external_id,role,active) VALUES(?,?,?,1)", (platform, str(t).strip(), "admin")); rb.db.conn.commit()
            st.pop("rubika_admin_mode", None)
            return rb.send(chat, "✅ مدیر جدید اضافه شد.", _menu(rb))

        # Top-level full admin actions.
        if t == "9":
            st["rubika_admin_mode"] = "service_select"
            return rb.send(chat, "🛠 باز/بسته خدمات\n🇮🇷 خدمات ایرانی و خدمات اتباع از همین بخش مدیریت می‌شوند.", _services(rb))
        if t == "10":
            st["rubika_admin_mode"] = "text_select"
            return rb.send(chat, "📝 تغییر متن‌ها\nهر گزینه را بزنید تا متن فعلی را ببینید و متن جدید را وارد کنید.", _texts())
        if t == "11":
            st["rubika_admin_mode"] = "admin_add"
            return rb.send(chat, "🔐 شناسه کاربر مدیر جدید را ارسال کنید.\nبعد از ارسال، دسترسی مدیریت برای روبیکا ثبت می‌شود.", [[("0", "⬅️ انصراف")]])
        if t == "12":
            # Clear only conversation state; keep language/admin identity.
            keep = {k: v for k, v in st.items() if k in ("lang", "admin")}
            rb.STATE[str(uid)] = keep
            return rb.send(chat, "🔄 ربات از نو شروع شد.\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید.", rb.main_rows(uid))
        if t == "0":
            keep = {k: v for k, v in st.items() if k in ("lang", "admin")}
            rb.STATE[str(uid)] = keep
            return rb.send(chat, rb.T(uid, "menu"), rb.main_rows(uid))

        # Let the existing, tested handlers process the remaining legacy admin actions.
        return None

    def handle_fixed(uid, chat, text, update=None):
        suid = str(uid)
        if rb.is_admin(suid):
            # The final router already converts keypad labels to ids.
            result = admin_action(suid, chat, str(text).strip())
            if result is not None:
                return result
        return old_handle(uid, chat, text, update)

    rb.handle = handle_fixed
    rb._netyar_rubika_admin_full = True
    log.info("full Rubika admin controller installed")
