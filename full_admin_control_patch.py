"""Full admin control layer for NetYar.

Adds persistent multi-admin management, per-service enable/disable, prices,
editable common texts, and service metadata without rewriting the existing bot.
"""
import os
import re
import logging

log = logging.getLogger("netyar.full_admin")


def _admins_from_env(existing=None):
    out = set(existing or set())
    raw = os.getenv("ADMIN_IDS", "")
    out.update(x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip())
    for k in ("ADMIN_ID_1", "ADMIN_ID_2"):
        v = os.getenv(k, "").strip()
        if v:
            out.add(v)
    return out


def _label(db, key, fallback):
    return db.setting("label_" + key, fallback) or fallback


def _service_rows(db):
    return db.conn.execute("SELECT * FROM services ORDER BY id").fetchall()


def _service_menu(B, uid):
    rows = []
    for s in _service_rows(B.db):
        state = "🟢 باز" if int(s["active"] or 0) else "🔴 بسته"
        rows.append([f"{state} {s['key']} | {s['name']}"])
    rows.append(["➕ افزودن خدمت", "✏️ ویرایش خدمت"])
    rows.append(["⬅️ بازگشت"])
    return B.kb(rows)


def _admin_menu(B):
    return B.kb([
        ["👤 پنل کاربران", "👥 همکاران"],
        ["💰 شارژها", "📋 درخواست‌ها"],
        ["⚙️ قیمت‌ها", "🔧 مدیریت خدمات"],
        ["📝 مدیریت متن‌ها", "👤 مدیران"],
        ["🤖 افزودن بات", "🤖 بات‌های متصل"],
        ["📊 گزارش", "📣 اعلان خدمت"],
        ["⬅️ منوی اصلی"],
    ])


def install():
    import bot as B
    if getattr(B, "_full_admin_control_installed", False):
        return

    # Persistent admin registry. Environment admins remain owners and cannot be
    # accidentally removed from the database UI.
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS admins(platform TEXT, external_id TEXT, role TEXT DEFAULT 'admin', active INTEGER DEFAULT 1, PRIMARY KEY(platform,external_id))")
    B.db.conn.commit()
    B.ADM = _admins_from_env(getattr(B, "ADM", set()))
    old_admin = B.admin

    def admin(uid):
        if str(uid) in B.ADM or B.S.get(uid, {}).get("admin") is True:
            return True
        try:
            r = B.db.conn.execute("SELECT 1 FROM admins WHERE platform='telegram' AND external_id=? AND active=1", (str(uid),)).fetchone()
            return bool(r)
        except Exception:
            return False

    B.admin = admin

    # Dynamic service visibility. The partner panel and administrative controls
    # stay visible; individual customer services can be closed independently.
    old_main = B.main
    def main(uid):
        markup = old_main(uid)
        # old_main may already be inline; rebuild only the visible service rows
        # using the same button objects/text where possible.
        try:
            active = {str(r["key"]): bool(r["active"]) for r in _service_rows(B.db)}
            names = {
                "fida": {"fa":"🪪 فیدای غیر حضوری","en":"🪪 FIDA service","ar":"🪪 خدمة فيدا"},
                "print": {"fa":"🖨 خدمات چاپ","en":"🖨 Printing","ar":"🖨 الطباعة"},
                "government": {"fa":"🏛 حل مشکل ورود اتباع دولت من","en":"🏛 Government access","ar":"🏛 خدمات الحكومة"},
            }
            # Reply/inline keyboard implementations expose .inline_keyboard or .keyboard.
            source = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None)
            if source is None:
                return markup
            rows = []
            for row in source:
                out=[]
                for btn in row:
                    text=getattr(btn,"text",str(btn))
                    key=None
                    for k,langs in names.items():
                        if text in langs.values() or text == _label(B.db,k,langs["fa"]): key=k; break
                    if key and not active.get(key, True): continue
                    out.append(btn)
                if out: rows.append(out)
            if hasattr(markup, "inline_keyboard"):
                from telegram import InlineKeyboardMarkup
                return InlineKeyboardMarkup(rows)
            return B.kb([[getattr(x,"text",str(x)) for x in row] for row in rows])
        except Exception:
            log.exception("dynamic service menu failed")
            return markup
    B.main = main

    # Common editable texts. Service names/prices remain in the database and are
    # immediately reflected in the service list and next request price.
    old_start = B.start
    async def start(update, context):
        uid=update.effective_user.id
        # Keep the existing language buttons but make the opening text editable.
        try:
            text=B.db.setting("welcome_fa","سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:")
            return await update.message.reply_text(text, reply_markup=__import__('telegram').InlineKeyboardMarkup([[__import__('telegram').InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa"),__import__('telegram').InlineKeyboardButton("🇬🇧 English",callback_data="lang:en"),__import__('telegram').InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar")]]))
        except Exception:
            return await old_start(update, context)
    B.start = start

    old_router = B.router
    async def router(update, context):
        uid=update.effective_user.id
        text=(getattr(update.message,"text","") or "").strip()
        st=B.S.setdefault(uid,{})
        if admin(uid):
            # Admin entry point always wins over customer labels.
            if text in {"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات"}:
                st["admin"] = True; st["admin_mode"] = None
                return await update.message.reply_text("🛠 پنل مدیریت کامل", reply_markup=_admin_menu(B))
            result = await _admin_flow(B, update, context, text, st)
            if result is not None:
                return result
        return await old_router(update, context)
    B.router = router

    # Admin callback operations for service toggles use normal Telegram buttons.
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        old_cb = B.admin_cb
        async def admin_cb(update, context):
            q=update.callback_query
            data=str(q.data or "")
            if data.startswith("svc:") and admin(q.from_user.id):
                await q.answer()
                _, key, action = data.split(":",2)
                if action == "toggle":
                    row=B.db.conn.execute("SELECT active FROM services WHERE key=?",(key,)).fetchone()
                    if not row:
                        return await q.message.reply_text("❌ خدمت پیدا نشد.",reply_markup=_admin_menu(B))
                    new=0 if int(row["active"] or 0) else 1
                    B.db.conn.execute("UPDATE services SET active=? WHERE key=?",(new,key));B.db.conn.commit()
                    return await q.message.reply_text(f"{'🟢 خدمت باز شد' if new else '🔴 خدمت بسته شد'}: {key}",reply_markup=_service_menu(B,q.from_user.id))
            return await old_cb(update, context)
        B.admin_cb = admin_cb
    except Exception:
        log.exception("admin callback wrapping failed")

    B._full_admin_control_installed=True
    log.info("full admin control installed")


async def _admin_flow(B, update, context, text, st):
    uid=update.effective_user.id
    mode=st.get("admin_mode")

    if text in {"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات"}:
        st["admin_mode"]=None
        return await update.message.reply_text("🛠 پنل مدیریت کامل",reply_markup=_admin_menu(B))

    if text=="⬅️ منوی اصلی":
        st["admin_mode"]=None
        return await update.message.reply_text("منوی اصلی",reply_markup=B.main(uid))

    if text=="🔧 مدیریت خدمات":
        st["admin_mode"]="services"; return await update.message.reply_text("🔧 مدیریت تک‌تک خدمات\nبرای باز/بسته کردن هر خدمت روی آن بزنید.",reply_markup=_service_menu(B,uid))

    if mode=="services":
        row=None
        for s in _service_rows(B.db):
            if str(s["key"]) in text: row=s; break
        if row:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            return await update.message.reply_text(
                f"🔧 {row['name']}\n💰 قیمت: {int(row['price'] or 0):,} تومان\n📌 وضعیت: {'باز' if row['active'] else 'بسته'}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 تغییر وضعیت",callback_data=f"svc:{row['key']}:toggle")],[InlineKeyboardButton("✏️ ویرایش نام و قیمت",callback_data=f"svc_edit:{row['key']}")]])
            )

    if text=="⚙️ قیمت‌ها":
        st["admin_mode"]="price";return await update.message.reply_text("💰 قیمت را با قالب زیر بفرستید:\ngovernment 500000\nprint 1000\nfida 500000",reply_markup=B.kb([["⬅️ بازگشت"]]))
    if mode=="price":
        p=text.split()
        if len(p)!=2 or not p[1].isdigit(): return await update.message.reply_text("❌ قالب درست: government 500000",reply_markup=B.kb([["⬅️ بازگشت"]]))
        key=p[0]; amount=int(p[1]);
        B.db.conn.execute("UPDATE services SET price=? WHERE key=?",(amount,key));B.db.set_setting("price_"+key,amount)
        return await update.message.reply_text(f"✅ قیمت {key} روی {amount:,} تومان تنظیم شد.",reply_markup=_admin_menu(B))

    if text=="📝 مدیریت متن‌ها":
        st["admin_mode"]="texts";return await update.message.reply_text("📝 متن قابل ویرایش را انتخاب کنید:",reply_markup=B.kb([["welcome_fa","welcome_en"],["welcome_ar","contact_text"],["⬅️ بازگشت"]]))
    if mode=="texts" and text in {"welcome_fa","welcome_en","welcome_ar","contact_text"}:
        st["text_key"]=text;st["admin_mode"]="text_value";return await update.message.reply_text(f"✏️ متن جدید برای {text} را ارسال کنید.",reply_markup=B.kb([["⬅️ بازگشت"]]))
    if mode=="text_value":
        key=st.get("text_key");B.db.set_setting(key,text);st["admin_mode"]="texts";return await update.message.reply_text("✅ متن ذخیره شد.",reply_markup=B.kb([["welcome_fa","welcome_en"],["welcome_ar","contact_text"],["⬅️ بازگشت"]]))

    if text=="👤 مدیران":
        st["admin_mode"]="admins";rows=B.db.conn.execute("SELECT * FROM admins ORDER BY platform,external_id").fetchall();env=sorted(B.ADM);lines=["👤 مدیران ثبت‌شده:"]+[f"• {r['external_id']} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows]+[f"• ENV: {x}" for x in env]
        return await update.message.reply_text("\n".join(lines),reply_markup=B.kb([["➕ افزودن مدیر","🗑 حذف مدیر"],["⬅️ بازگشت"]]))
    if mode=="admins" and text=="➕ افزودن مدیر":
        st["admin_mode"]="add_admin";return await update.message.reply_text("👤 شناسه عددی تلگرام مدیر جدید را ارسال کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
    if mode=="add_admin":
        if not text.isdigit(): return await update.message.reply_text("❌ شناسه باید عددی باشد.")
        B.db.conn.execute("INSERT OR REPLACE INTO admins(platform,external_id,role,active) VALUES('telegram',?,'admin',1)",(text,));B.db.conn.commit();B.ADM.add(text);return await update.message.reply_text("✅ مدیر دوم به‌صورت دائمی ثبت شد.",reply_markup=_admin_menu(B))
    if mode=="admins" and text=="🗑 حذف مدیر":
        st["admin_mode"]="remove_admin";return await update.message.reply_text("👤 شناسه عددی مدیر را ارسال کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
    if mode=="remove_admin":
        B.db.conn.execute("UPDATE admins SET active=0 WHERE platform='telegram' AND external_id=?",(text,));B.db.conn.commit();B.ADM.discard(text);return await update.message.reply_text("✅ دسترسی مدیر حذف شد.",reply_markup=_admin_menu(B))

    if text=="🤖 بات‌های متصل":
        rows=B.db.bots();return await update.message.reply_text("🤖 بات‌های متصل\n\n"+("\n".join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or "موردی ثبت نشده است."),reply_markup=_admin_menu(B))

    if text=="📊 گزارش":
        c1=B.db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0];c2=B.db.conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0];c3=B.db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        return await update.message.reply_text(f"📊 گزارش\n👤 کاربران: {c1}\n👥 همکاران: {c2}\n📋 درخواست‌ها: {c3}",reply_markup=_admin_menu(B))

    return None
