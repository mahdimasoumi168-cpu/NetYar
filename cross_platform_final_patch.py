"""Final cross-platform UX/admin compatibility layer.

Keeps Telegram/Rubika core handlers intact while fixing Rubika keypad routing
and providing a real, database-backed admin menu for the features already
represented by the shared schema.
"""
import logging
import re

log = logging.getLogger("netyar.cross_platform_final")


def _digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _money(value):
    raw = _digits(value).replace(",", "").replace("٬", "").replace(" ", "")
    return int(raw) if raw.isdigit() else None


def _rubika_alias(step, text):
    """Return the exact Persian command expected by rubika_v2.handle."""
    x = str(text or "").strip()
    numeric = {
        "language": {"1": "🇮🇷 فارسی", "2": "🇬🇧 English", "3": "🇸🇦 العربية"},
        "citizenship": {"1": "🪪 اتباع هستم", "2": "🇮🇷 ایرانی هستم"},
        "iranian": {"1": "👥 پنل همکاران", "2": "🎫 پیگیری", "0": "❌ انصراف"},
        "menu": {"1": "🪪 فیدای غیر حضوری", "2": "🖨 خدمات چاپ", "3": "🏛 حل مشکل ورود اتباع دولت من", "4": "🎫 پیگیری", "5": "📱 خدمات سیم کارت", "6": "📝 آزمون غربالگری", "7": "💰 کیف پول من", "8": "👥 پنل همکاران", "9": "📞 تماس با ما", "0": "❌ انصراف"},
        "partner": {"1": "➕ شارژ حساب", "2": "🔎 پیگیری کد", "3": "📋 سوابق", "4": "💰 موجودی", "5": "🏛 حل مشکل سامانه دولت من", "0": "❌ انصراف"},
        "admin": {},
    }
    if x in numeric.get(step, {}):
        return numeric[step][x]
    aliases = {
        "👥 پنل همکاران": "👥 پنل همکاران", "پنل همکاران": "👥 پنل همکاران",
        "🔵 👥 پنل همکاران": "👥 پنل همکاران", "🎫 پیگیری": "🎫 پیگیری", "پیگیری": "🎫 پیگیری",
        "❌ انصراف": "❌ انصراف", "انصراف": "❌ انصراف", "❌ لغو": "❌ انصراف", "لغو": "❌ انصراف",
        "📱 خدمات سیم کارت": "📱 خدمات سیم کارت", "خدمات سیم کارت": "📱 خدمات سیم کارت",
        "📝 آزمون غربالگری و پیگیری": "📝 آزمون غربالگری", "📝 آزمون غربالگری": "📝 آزمون غربالگری",
        "🏛 حل مشکل ورود اتباع دولت من": "🏛 حل مشکل ورود اتباع دولت من",
        "🪪 فیدای غیر حضوری": "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ": "🖨 خدمات چاپ",
        "📞 تماس با ما": "📞 تماس با ما", "💰 کیف پول من": "💰 کیف پول من",
    }
    return aliases.get(x, x)


def _admin_rows():
    return [
        [("1", "👥 مدیریت همکاران"), ("2", "📋 درخواست‌ها")],
        [("3", "🔧 مدیریت خدمات"), ("4", "💰 قیمت خدمات")],
        [("5", "📝 مدیریت متن‌ها"), ("6", "👤 مدیریت مدیران")],
        [("7", "💳 شارژها"), ("8", "📊 گزارش‌ها")],
        [("9", "🤖 مدیریت بات‌ها"), ("10", "🔄 شروع مجدد")],
        [("0", "⬅️ منوی اصلی")],
    ]


def _service_rows(db, group=None):
    rows = []
    services = db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall()
    for r in services:
        name = str(r["name"] or r["key"])
        prefix = "🟢" if int(r["active"] or 0) else "🔴"
        rows.append([(str(r["key"]), f"{prefix} {name} | {int(r['price'] or 0):,}")])
    rows.append([("0", "⬅️ بازگشت")])
    return rows


def _install_rubika(rb):
    if getattr(rb, "_cross_platform_final_installed", False):
        return
    old_handle = rb.handle
    old_admin = getattr(rb, "admin", None)

    def admin_panel(uid, chat):
        rb.STATE.setdefault(str(uid), {}).update({"step": "admin", "admin_mode": "root"})
        return rb.send(chat, "🛠 پنل مدیریت کامل\nهمه بخش‌های قابل مدیریت را از اینجا انتخاب کنید:", _admin_rows())

    def admin_action(uid, chat, x):
        st = rb.STATE.setdefault(str(uid), {})
        x = str(x).strip()
        db = rb.db
        if x in {"0", "⬅️ منوی اصلی", "🔄 شروع مجدد"}:
            st.clear(); st.update({"lang": "fa", "step": "menu"})
            return rb.send(chat, rb.T(uid, "menu"), rb.main_rows(uid))
        if x in {"1", "👥 مدیریت همکاران"}:
            n = db.conn.execute("SELECT COUNT(*) c FROM partners WHERE active=1").fetchone()["c"]
            return rb.send(chat, f"👥 مدیریت همکاران\nتعداد همکاران فعال: {n}\n\n➕ برای افزودن همکار، شماره و رمز از پنل اصلی مدیریت ثبت شود.", [[("0", "⬅️ بازگشت")]])
        if x in {"2", "📋 درخواست‌ها"}:
            rows = db.conn.execute("SELECT tracking_code,service_key,platform,status,amount,created_at FROM requests ORDER BY id DESC LIMIT 15").fetchall()
            if not rows:
                text = "📋 هنوز درخواستی ثبت نشده است."
            else:
                text = "📋 آخرین درخواست‌ها:\n\n" + "\n".join(f"🎫 {r['tracking_code']} | {r['service_key']} | {r['platform']} | {r['status']} | {int(r['amount'] or 0):,} تومان" for r in rows)
            return rb.send(chat, text, [[("0", "⬅️ بازگشت")]])
        if x in {"3", "🔧 مدیریت خدمات"}:
            st["admin_mode"] = "services"; return rb.send(chat, "🔧 مدیریت خدمات\n🟢 باز | 🔴 بسته\nروی خدمت موردنظر بزنید:", _service_rows(db))
        if x in {"4", "💰 قیمت خدمات"}:
            st["admin_mode"] = "prices"; return rb.send(chat, "💰 قیمت خدمات\nخدمت را انتخاب کنید:", _service_rows(db))
        if x in {"5", "📝 مدیریت متن‌ها"}:
            return rb.send(chat, "📝 مدیریت متن‌ها\n\n1️⃣ متن خوش‌آمدگویی فارسی\n2️⃣ متن خوش‌آمدگویی انگلیسی\n3️⃣ متن خوش‌آمدگویی عربی\n4️⃣ پیام پشتیبانی\n\nشماره موردنظر را ارسال کنید.", [[("1", "1️⃣ فارسی"), ("2", "2️⃣ English")], [("3", "3️⃣ العربية"), ("4", "4️⃣ پشتیبانی")], [("0", "⬅️ بازگشت")]])
        if x in {"6", "👤 مدیریت مدیران"}:
            n = db.conn.execute("SELECT COUNT(*) c FROM admins WHERE active=1").fetchone()["c"]
            st["admin_mode"] = "admins"; return rb.send(chat, f"👤 مدیران فعال: {n}\n\nبرای افزودن مدیر، شناسه عددی مدیر را ارسال کنید.", [[("1", "➕ افزودن مدیر")], [("0", "⬅️ بازگشت")]])
        if x in {"7", "💳 شارژها"}:
            rows = db.conn.execute("SELECT id,partner_id,amount,status,created_at FROM topups ORDER BY id DESC LIMIT 15").fetchall()
            text = "💳 شارژها:\n\n" + ("\n".join(f"#{r['id']} | همکار {r['partner_id']} | {int(r['amount'] or 0):,} | {r['status']}" for r in rows) if rows else "شارژی ثبت نشده است.")
            return rb.send(chat, text, [[("0", "⬅️ بازگشت")]])
        if x in {"8", "📊 گزارش‌ها"}:
            q = db.conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            r = db.conn.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
            p = db.conn.execute("SELECT COUNT(*) c FROM partners WHERE active=1").fetchone()["c"]
            return rb.send(chat, f"📊 گزارش کلی\n\n👤 کاربران: {q}\n📋 درخواست‌ها: {r}\n👥 همکاران فعال: {p}", [[("0", "⬅️ بازگشت")]])
        if x in {"9", "🤖 مدیریت بات‌ها"}:
            rows = db.bots(); text = "🤖 بات‌های متصل:\n\n" + ("\n".join(f"• {r['platform']} — {r['bot_name']} — {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) if rows else "هنوز باتی ثبت نشده است.")
            return rb.send(chat, text, [[("0", "⬅️ بازگشت")]])
        if x in {"10", "🔄 شروع مجدد"}:
            st.clear(); st.update({"lang": "fa", "step": "menu"}); return rb.send(chat, rb.T(uid, "menu"), rb.main_rows(uid))
        return rb.send(chat, "⏳ این بخش در حال آماده‌سازی است.", _admin_rows())

    def handle(uid, chat, x, update):
        uid = str(uid); st = rb.STATE.setdefault(uid, {})
        raw = str(x or "").strip()
        step = st.get("step", "")
        x2 = _rubika_alias(step, raw)
        # Normalize keypad ids and labels before the legacy handler sees them.
        if st.get("admin_mode") == "root" or step == "admin":
            return admin_action(uid, chat, x2)
        if st.get("admin_mode") in {"services", "prices", "admins"}:
            # Service buttons carry the service key as their id; keep a small, deterministic editor.
            if x2 in {"0", "⬅️ بازگشت"}:
                st["admin_mode"] = "root"; return rb.send(chat, "🛠 پنل مدیریت کامل", _admin_rows())
            if st.get("admin_mode") == "services":
                row = rb.db.conn.execute("SELECT key,name,price,active FROM services WHERE key=?", (raw,)).fetchone()
                if row:
                    new = 0 if int(row["active"] or 0) else 1
                    rb.db.conn.execute("UPDATE services SET active=? WHERE key=?", (new, raw)); rb.db.conn.commit()
                    return rb.send(chat, f"{'🟢 خدمت باز شد.' if new else '🔴 خدمت بسته شد.'}\n{row['name']}", _service_rows(rb.db))
            if st.get("admin_mode") == "prices":
                row = rb.db.conn.execute("SELECT key,name,price FROM services WHERE key=?", (raw,)).fetchone()
                if row:
                    st.update({"admin_mode": "price_value", "service_key": raw}); return rb.send(chat, f"💰 قیمت جدید «{row['name']}» را به تومان ارسال کنید.", [[("0", "⬅️ بازگشت")]])
        if st.get("admin_mode") == "price_value":
            amount = _money(raw)
            if amount is None: return rb.send(chat, "❌ مبلغ باید فقط عدد باشد.", [[("0", "⬅️ بازگشت")]])
            key = st.get("service_key"); rb.db.conn.execute("UPDATE services SET price=? WHERE key=?", (amount, key)); rb.db.set_setting("price_" + str(key), amount); st["admin_mode"] = "root"; return rb.send(chat, f"✅ قیمت به {amount:,} تومان تغییر کرد.", _admin_rows())
        if st.get("admin_mode") == "admins":
            if raw == "1": st["admin_mode"] = "admin_id"; return rb.send(chat, "👤 شناسه عددی مدیر جدید را ارسال کنید.", [[("0", "⬅️ بازگشت")]])
        if st.get("admin_mode") == "admin_id":
            if not _digits(raw).isdigit(): return rb.send(chat, "❌ شناسه باید عددی باشد.")
            rb.db.conn.execute("INSERT OR REPLACE INTO admins(platform,external_id,role,active) VALUES(?,?,?,1)", ("rubika", _digits(raw), "admin")); rb.db.conn.commit(); st["admin_mode"] = "root"; return rb.send(chat, "✅ مدیر روبیکا اضافه شد.", _admin_rows())
        # Global restart/cancel: never leave stale state behind.
        if x2 == "❌ انصراف":
            lang = st.get("lang", "fa"); st.clear(); st.update({"lang": lang, "step": "menu"}); return rb.send(chat, rb.T(uid, "cancel"), rb.main_rows(uid))
        if x2 in {"🔄 شروع مجدد", "شروع مجدد", "/start"}:
            st.clear(); st.update({"lang": "fa", "step": "language"}); return rb.send(chat, rb.T(uid, "lang"), [[("1", "🇮🇷 فارسی")], [("2", "🇬🇧 English")], [("3", "🇸🇦 العربية")]])
        # If a displayed keypad label is slightly different, feed the canonical label to the legacy handler.
        return old_handle(uid, chat, x2, update)

    rb.handle = handle
    rb.admin_rows = _admin_rows
    rb._cross_platform_final_installed = True
    log.info("cross-platform final patch installed for Rubika")


def install():
    try:
        import rubika_v2 as rb
        _install_rubika(rb)
    except Exception:
        log.exception("failed to install Rubika cross-platform patch")
