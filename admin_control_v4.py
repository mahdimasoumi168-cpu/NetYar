"""Long-term, database-driven control center for NetYar.

The goal is to move operational configuration out of source code: texts, prices,
service availability, support contact, admins and basic platform switches are
stored in SQLite and can be changed from the admin panel without a code edit.
This module is intentionally additive and monkey-patches the existing admin
entry points rather than replacing the service engine.
"""
import os
import logging
import re
from core import db, now, hash_password

log = logging.getLogger("netyar.admin_control_v4")
INSTALLED = False

PREFIX = "cfg."
DEFAULTS = {
    "support_id": "@Good_ok_2000",
    "support_text": "📞 پشتیبانی: @Good_ok_2000",
    "restart_text": "🔄 شروع مجدد",
    "disabled_text": "⏳ این بخش فعلاً بسته است.",
    "admin_title": "🛠 پنل مدیریت بات",
    "currency": "تومان",
    "telegram_enabled": "1",
    "rubika_enabled": "1",
    "bale_enabled": "0",
    "eitaa_enabled": "0",
}


def _ensure_schema():
    db.conn.executescript("""
    CREATE TABLE IF NOT EXISTS admin_settings(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admin_texts(
        key TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        value TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS service_groups(
        service_key TEXT PRIMARY KEY,
        group_name TEXT NOT NULL DEFAULT 'foreign',
        enabled INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admin_roles(
        platform TEXT NOT NULL,
        external_id TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        PRIMARY KEY(platform, external_id)
    );
    """)
    for k, v in DEFAULTS.items():
        db.conn.execute(
            "INSERT OR IGNORE INTO admin_settings(key,value,updated_at) VALUES(?,?,?)",
            (k, v, now()),
        )
    # Existing services get a group automatically; names are only defaults and
    # remain editable through the service editor.
    for row in db.conn.execute("SELECT key FROM services").fetchall():
        key = str(row["key"])
        group = "iranian" if key in {"iranian", "iranian_tracking"} else "foreign"
        db.conn.execute(
            "INSERT OR IGNORE INTO service_groups(service_key,group_name,enabled,updated_at) VALUES(?,?,1,?)",
            (key, group, now()),
        )
    db.conn.commit()


def setting(key, default=""):
    row = db.conn.execute("SELECT value FROM admin_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db.conn.execute(
        "INSERT OR REPLACE INTO admin_settings(key,value,updated_at) VALUES(?,?,?)",
        (key, str(value), now()),
    )
    db.conn.commit()


def _admins():
    rows = db.conn.execute(
        "SELECT platform,external_id,role,active FROM admins ORDER BY platform,external_id"
    ).fetchall()
    return rows


def _save_admin(platform, external_id, role="admin"):
    db.conn.execute(
        "INSERT OR REPLACE INTO admins(platform,external_id,role,active) VALUES(?,?,?,1)",
        (platform, str(external_id), role),
    )
    db.conn.execute(
        "INSERT OR REPLACE INTO admin_roles(platform,external_id,role,active,created_at) VALUES(?,?,?,?,?)",
        (platform, str(external_id), role, 1, now()),
    )
    db.conn.commit()


def _service_rows():
    return db.conn.execute("""
        SELECT s.id,s.key,s.name,s.description,s.price,s.active,
               COALESCE(g.group_name,'foreign') group_name,
               COALESCE(g.enabled,s.active) enabled
        FROM services s LEFT JOIN service_groups g ON g.service_key=s.key
        ORDER BY s.id
    """).fetchall()


def _set_service(key, enabled=None, price=None, name=None, description=None, group=None):
    row = db.conn.execute("SELECT * FROM services WHERE key=?", (key,)).fetchone()
    if not row:
        db.conn.execute(
            "INSERT INTO services(key,name,description,price,active) VALUES(?,?,?,?,1)",
            (key, name or key, description or "", int(price or 0)),
        )
    else:
        if price is not None:
            db.conn.execute("UPDATE services SET price=? WHERE key=?", (int(price), key))
        if name is not None:
            db.conn.execute("UPDATE services SET name=? WHERE key=?", (name, key))
        if description is not None:
            db.conn.execute("UPDATE services SET description=? WHERE key=?", (description, key))
        if enabled is not None:
            db.conn.execute("UPDATE services SET active=? WHERE key=?", (1 if enabled else 0, key))
    if group is None:
        group = db.conn.execute("SELECT group_name FROM service_groups WHERE service_key=?", (key,)).fetchone()
        group = group["group_name"] if group else "foreign"
    db.conn.execute(
        "INSERT OR REPLACE INTO service_groups(service_key,group_name,enabled,updated_at) VALUES(?,?,?,?)",
        (key, group, 1 if enabled is None else int(bool(enabled)), now()),
    )
    db.conn.commit()


def _menu(B):
    return B.kb([
        ["👥 کاربران", "🤝 همکاران"],
        ["📋 درخواست‌ها", "🎫 تیکت‌ها"],
        ["🟢/🔴 خدمات", "💰 قیمت خدمات"],
        ["📝 متن‌های ربات", "📎 مدارک و فایل‌ها"],
        ["👤 مدیران", "🤖 پیام‌رسان‌ها"],
        ["📊 گزارش‌ها", "⚙️ تنظیمات پایه"],
        ["📞 پشتیبانی", "⬅️ منوی اصلی"],
    ])


def _service_menu(B):
    rows = []
    for r in _service_rows():
        icon = "🟢" if int(r["enabled"]) else "🔴"
        group = "🇮🇷 ایرانی" if r["group_name"] == "iranian" else "🇦🇫 اتباع"
        rows.append([f"{icon} {group} | {r['name']}"])
    rows.append(["➕ افزودن خدمت", "🔧 ویرایش خدمت"])
    rows.append(["⬅️ بازگشت"])
    return B.kb(rows)


def _text_menu(B):
    rows = [["👋 خوش‌آمدگویی", "🌐 انتخاب زبان"],
            ["🇮🇷 متن ایرانی", "🇦🇫 متن اتباع"],
            ["📞 پشتیبانی", "❌ خطاها"],
            ["🔄 شروع مجدد", "⏳ خدمت بسته"],
            ["⬅️ بازگشت"]]
    return B.kb(rows)


def _price_menu(B):
    rows = []
    for r in _service_rows():
        rows.append([f"💰 {r['key']} | {r['price']:,} تومان"])
    rows.append(["⬅️ بازگشت"])
    return B.kb(rows)


def _msg(B, text, markup=None):
    return text, markup


def _admin_text_wrapper(B):
    original = getattr(B, "admin_text", None)
    if original is None or getattr(original, "_admin_v4", False):
        return

    async def wrapped(u, c):
        uid = u.effective_user.id
        st = B.S.setdefault(uid, {})
        t = (u.message.text or "").strip()
        mode = st.get("mode", "")
        if not B.admin(uid):
            return await original(u, c)

        if t in {"🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "/Admin2025"}:
            st["mode"] = "cc_menu"
            return await u.message.reply_text(setting("admin_title", DEFAULTS["admin_title"]), reply_markup=_menu(B))
        if t == "🟢/🔴 خدمات":
            st["mode"] = "cc_services"; return await u.message.reply_text("🛠 مدیریت باز/بسته بودن خدمات\nهر خدمت را برای تغییر وضعیت انتخاب کنید:", reply_markup=_service_menu(B))
        if t == "💰 قیمت خدمات":
            st["mode"] = "cc_prices"; return await u.message.reply_text("💰 قیمت هر خدمت را انتخاب کنید:", reply_markup=_price_menu(B))
        if t == "📝 متن‌های ربات":
            st["mode"] = "cc_texts"; return await u.message.reply_text("📝 متن موردنظر برای ویرایش را انتخاب کنید:", reply_markup=_text_menu(B))
        if t == "👤 مدیران":
            st["mode"] = "cc_admins"; rows=[[f"👤 {r['platform']}:{r['external_id']} ({r['role']})"] for r in _admins()]; rows += [["➕ افزودن مدیر"],["⬅️ بازگشت"]]; return await u.message.reply_text("👤 مدیریت مدیران\nمدیر جدید را می‌توان از همین بخش اضافه کرد.", reply_markup=B.kb(rows))
        if t == "📞 پشتیبانی":
            st["mode"] = "cc_support"; return await u.message.reply_text(f"📞 شناسه پشتیبانی فعلی: {setting('support_id', '@Good_ok_2000')}\nشناسه جدید را ارسال کنید:", reply_markup=B.cancel_kb())
        if t == "⚙️ تنظیمات پایه":
            st["mode"] = "cc_base"; return await u.message.reply_text("⚙️ تنظیمات پایه\nمقدار موردنظر را انتخاب کنید:", reply_markup=B.kb([["📞 پشتیبانی"],["🔄 متن شروع مجدد"],["⏳ متن خدمت بسته"],["💳 شماره کارت"],["👤 صاحب کارت"],["⬅️ بازگشت"]]))
        if t == "👥 کاربران":
            n=db.conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]; return await u.message.reply_text(f"👥 تعداد کاربران: {n}", reply_markup=_menu(B))
        if t == "🤝 همکاران":
            rows=db.conn.execute("SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC LIMIT 50").fetchall(); txt="\n".join(f"#{r['id']} | {r['name']} | {r['phone']} | {r['balance']:,}" for r in rows) or "همکاری ثبت نشده است."; return await u.message.reply_text("🤝 همکاران\n\n"+txt, reply_markup=_menu(B))
        if t == "📋 درخواست‌ها":
            rows=db.conn.execute("SELECT tracking_code,service_key,status,amount,platform FROM requests ORDER BY id DESC LIMIT 30").fetchall(); txt="\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,} | {r['platform']}" for r in rows) or "درخواستی نیست."; return await u.message.reply_text("📋 درخواست‌ها\n\n"+txt, reply_markup=_menu(B))
        if t == "📊 گزارش‌ها":
            q=db.conn.execute("SELECT COUNT(*) requests, COALESCE(SUM(amount),0) amount FROM requests").fetchone(); s=db.conn.execute("SELECT COUNT(*) n FROM services WHERE active=1").fetchone()["n"]; return await u.message.reply_text(f"📊 گزارش\nدرخواست‌ها: {q['requests']}\nمجموع مبالغ: {q['amount']:,} تومان\nخدمات فعال: {s}", reply_markup=_menu(B))
        if t == "⬅️ بازگشت":
            st["mode"] = None; return await u.message.reply_text("🛠 پنل مدیریت", reply_markup=_menu(B))

        if mode == "cc_support":
            v=t.strip()
            if not v.startswith("@") and not re.fullmatch(r"[A-Za-z0-9_]{3,}", v): return await u.message.reply_text("❌ شناسه نامعتبر است.", reply_markup=B.cancel_kb())
            set_setting("support_id", v); set_setting("support_text", f"📞 پشتیبانی: {v}"); st["mode"]="cc_menu"; return await u.message.reply_text("✅ شناسه پشتیبانی ذخیره شد.", reply_markup=_menu(B))
        if mode == "cc_prices":
            m=re.match(r"^💰\s*([^|]+)\|\s*([0-9,]+)", t)
            if m:
                key=m.group(1).strip(); amount=int(m.group(2).replace(",","")); _set_service(key, price=amount); st["mode"]="cc_prices"; return await u.message.reply_text("✏️ مبلغ جدید را فقط به عدد ارسال کنید:", reply_markup=B.cancel_kb())
            if t.isdigit():
                key=st.get("price_key")
                if key: _set_service(key, price=int(t)); st["mode"]="cc_prices"; return await u.message.reply_text("✅ قیمت ذخیره شد.", reply_markup=_price_menu(B))
        if mode == "cc_texts":
            title_map={"👋 خوش‌آمدگویی":"welcome_fa","🌐 انتخاب زبان":"language","🇮🇷 متن ایرانی":"iranian","🇦🇫 متن اتباع":"foreign","📞 پشتیبانی":"support_text","❌ خطاها":"disabled_text","🔄 شروع مجدد":"restart_text","⏳ خدمت بسته":"disabled_text"}
            key=title_map.get(t)
            if key:
                st["text_key"]=key; st["mode"]="cc_text_value"; current=setting(key, DEFAULTS.get(key,"")); return await u.message.reply_text(f"📝 ویرایش متن\n\nمتن فعلی:\n{current}\n\n✏️ متن جدید را کامل ارسال کنید:", reply_markup=B.cancel_kb())
        if mode == "cc_text_value":
            key=st.get("text_key")
            if key:
                set_setting(key,t); st["mode"]="cc_texts"; return await u.message.reply_text("✅ متن با موفقیت ذخیره شد.", reply_markup=_text_menu(B))
        if mode == "cc_admins" and t == "➕ افزودن مدیر":
            st["mode"]="cc_admin_platform"; return await u.message.reply_text("پیام‌رسان مدیر را بنویسید: Telegram یا Rubika", reply_markup=B.cancel_kb())
        if mode == "cc_admin_platform":
            p="telegram" if t.lower() in {"telegram","تلگرام"} else "rubika" if t.lower() in {"rubika","روبیکا"} else None
            if not p:return await u.message.reply_text("❌ فقط Telegram یا Rubika را وارد کنید.", reply_markup=B.cancel_kb())
            st["admin_platform"]=p;st["mode"]="cc_admin_id";return await u.message.reply_text("شناسه عددی مدیر را ارسال کنید:", reply_markup=B.cancel_kb())
        if mode == "cc_admin_id":
            if not t.isdigit():return await u.message.reply_text("❌ شناسه باید عددی باشد.", reply_markup=B.cancel_kb())
            _save_admin(st.get("admin_platform","telegram"),t);st["mode"]="cc_admins";return await u.message.reply_text("✅ مدیر اضافه شد.", reply_markup=_menu(B))
        if mode == "cc_base":
            keymap={"📞 پشتیبانی":"support_id","🔄 متن شروع مجدد":"restart_text","⏳ متن خدمت بسته":"disabled_text","💳 شماره کارت":"card_number","👤 صاحب کارت":"card_owner"}
            key=keymap.get(t)
            if key:
                st["base_key"]=key;st["mode"]="cc_base_value";return await u.message.reply_text(f"مقدار فعلی: {setting(key, db.setting(key,''))}\n\nمقدار جدید را ارسال کنید:", reply_markup=B.cancel_kb())
        if mode == "cc_base_value":
            key=st.get("base_key")
            if key:
                set_setting(key,t); 
                if key in {"card_number","card_owner"}: db.set_setting(key,t)
                st["mode"]="cc_base";return await u.message.reply_text("✅ تنظیم ذخیره شد.", reply_markup=B.kb([["📞 پشتیبانی"],["🔄 متن شروع مجدد"],["⏳ متن خدمت بسته"],["💳 شماره کارت"],["👤 صاحب کارت"],["⬅️ بازگشت"]]))
        return await original(u,c)
    wrapped._admin_v4=True
    B.admin_text=wrapped


def install():
    global INSTALLED
    if INSTALLED:return
    _ensure_schema()
    try:
        import bot as B
        B.amenu=lambda: _menu(B)
        _admin_text_wrapper(B)
    except Exception:
        log.exception("Telegram admin control center installation failed")
    INSTALLED=True
    log.info("Long-term admin control center installed")
