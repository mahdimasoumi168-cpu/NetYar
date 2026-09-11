"""Production final compatibility layer.

Keeps the existing handlers intact while fixing callback persistence, stale
Telegram buttons, per-service admin controls, editable labels, and support.
"""
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger("netyar.production_final")

CATALOG = {
    "fida": {"fa": "🪪 فیدای غیر حضوری", "en": "🪪 FIDA service", "ar": "🪪 خدمة فيدا"},
    "print": {"fa": "🖨 خدمات چاپ", "en": "🖨 Printing", "ar": "🖨 الطباعة"},
    "government": {"fa": "🏛 حل مشکل ورود اتباع دولت من", "en": "🏛 Government access", "ar": "🏛 خدمات الحكومة"},
    "renewal": {"fa": "🎫 کد رهگیری تمدید کارت‌ها", "en": "🎫 Card renewal tracking", "ar": "🎫 متابعة تجديد البطاقات"},
    "sim": {"fa": "📱 خدمات سیم کارت", "en": "📱 SIM services", "ar": "📱 خدمات الشريحة"},
    "screening": {"fa": "📝 آزمون غربالگری", "en": "📝 Screening test", "ar": "📝 اختبار الفحص"},
    "tracking": {"fa": "🎫 پیگیری", "en": "🎫 Follow-up", "ar": "🎫 المتابعة"},
    "wallet": {"fa": "💰 کیف پول من", "en": "💰 My wallet", "ar": "💰 محفظتي"},
    "contact": {"fa": "📞 تماس با ما", "en": "📞 Contact us", "ar": "📞 اتصل بنا"},
    "complaint": {"fa": "📝 ثبت شکایت مشتریان", "en": "📝 Customer complaint", "ar": "📝 شكوى العميل"},
}


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _active(B, key):
    return B.db.setting("service_active_" + key, "1") == "1"


def _label(B, key, lang):
    return B.db.setting("service_label_{}_{}".format(key, lang), CATALOG[key].get(lang, CATALOG[key]["fa"]))


def _price(B, key):
    row = B.db.conn.execute("SELECT price FROM services WHERE key=?", (key,)).fetchone()
    if row:
        return int(row["price"] or 0)
    return int(B.db.setting("service_price_" + key, B.db.setting("price_" + key, "0")) or 0)


def _sync_catalog(B):
    for key, labels in CATALOG.items():
        B.db.conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            ("service_active_" + key, "1"),
        )
        for lang, text in labels.items():
            B.db.conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                ("service_label_{}_{}".format(key, lang), text),
            )
        B.db.conn.execute(
            "INSERT OR IGNORE INTO services(key,name,description,price,active) VALUES(?,?,?,?,1)",
            (key, labels["fa"], "", int(B.db.setting("service_price_" + key, B.db.setting("price_" + key, "0")) or 0)),
        )
    B.db.conn.commit()


def _menu_rows(B, uid):
    lang = B.S.get(uid, {}).get("lang", "fa")
    rows = []
    keys = ["fida", "print", "government", "renewal", "sim", "screening", "tracking", "wallet", "contact", "complaint"]
    visible = [k for k in keys if _active(B, k)]
    for i in range(0, len(visible), 2):
        rows.append([_label(B, visible[i], lang)] + ([_label(B, visible[i + 1], lang)] if i + 1 < len(visible) else []))
    rows.append(["🔵 👥 پنل همکاران"])
    if B.admin(uid):
        rows.append(["🔵 🛠 پنل مدیریت بات"])
    rows.append([B.CANCEL])
    return rows


def _service_admin_rows(B):
    rows = []
    for key in CATALOG:
        state = "🟢 باز" if _active(B, key) else "🔴 بسته"
        rows.append(["{} {} | {}".format(state, key, _label(B, key, "fa"))])
    rows.append(["⬅️ منوی مدیریت"])
    return rows


def install():
    import bot as B
    import final_ui_flow_patch as F
    import telegram_runtime as TG
    from telegram import CallbackQueryHandler

    if getattr(B, "_production_final_installed", False):
        return

    # Persistent callback table. Tokens are valid across Railway restarts.
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS ui_callbacks(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,label TEXT NOT NULL,created_at TEXT NOT NULL)")
    B.db.conn.commit()

    old_remember = F._remember
    def remember(uid, label):
        token = old_remember(uid, label)
        try:
            B.db.conn.execute(
                "INSERT OR REPLACE INTO ui_callbacks(token,user_id,label,created_at) VALUES(?,?,?,?)",
                (token, str(uid), str(label), B.now()),
            )
            B.db.conn.commit()
        except Exception:
            log.exception("callback persistence failed")
        return token
    F._remember = remember

    # Replace the registered stale callback handler with a persistent one.
    async def persistent_ui_callback(update, context):
        q = update.callback_query
        await q.answer()
        token = str(q.data or "")
        row = None
        try:
            row = B.db.conn.execute("SELECT label FROM ui_callbacks WHERE token=?", (token,)).fetchone()
        except Exception:
            log.exception("callback lookup failed")
        if not row:
            # Never expose the old expired/invalid wording. Rebuild a fresh menu.
            return await q.message.reply_text("🔄 منو به‌روزرسانی شد. لطفاً از گزینه‌های جدید استفاده کنید:", reply_markup=B.main(q.from_user.id))
        label = str(row["label"])
        fake = F._fake_update(update, label)
        try:
            result = await B.router(fake, context)
            if result is None:
                result = await B.ptext(fake, context)
                if result is None:
                    await B.service_text(fake, context)
        except Exception:
            log.exception("persistent callback failed: %s", label)
            await q.message.reply_text("❌ اجرای گزینه با خطا روبه‌رو شد. لطفاً دوباره انتخاب کنید.", reply_markup=B.main(q.from_user.id))

    old_build = TG.build
    def build():
        app = old_build()
        # Remove every previously registered ui:* callback handler so the old
        # stale-token handler cannot win before the persistent handler.
        for group, handlers in list(app.handlers.items()):
            app.handlers[group] = [h for h in handlers if not (isinstance(h, CallbackQueryHandler) and str(getattr(getattr(h, "pattern", None), "pattern", getattr(h, "pattern", ""))) == "^ui:")]
        app.add_handler(CallbackQueryHandler(persistent_ui_callback, pattern=r"^ui:"))
        return app
    TG.build = build

    _sync_catalog(B)

    # Stable Telegram main menu. No process-global current user is used for
    # deciding which services are visible.
    def main(uid):
        B._ui_current_uid = uid
        return B.kb(_menu_rows(B, uid))
    B.main = main

    old_router = B.router
    async def router(update, context):
        uid = update.effective_user.id
        text = (getattr(update.message, "text", "") or "").strip()
        st = B.S.setdefault(uid, {})
        if B.admin(uid):
            mode = st.get("production_admin_mode")
            if text in {"🔧 مدیریت خدمات", "🛠 مدیریت خدمات"}:
                st["production_admin_mode"] = "services"
                return await update.message.reply_text("🔧 مدیریت تک‌تک خدمات\n🟢 باز = فعال | 🔴 بسته = غیرفعال\nروی هر خدمت بزنید:", reply_markup=B.kb(_service_admin_rows(B)))
            if mode == "services":
                if text == "⬅️ منوی مدیریت":
                    st["production_admin_mode"] = None
                    return await update.message.reply_text("🛠 پنل مدیریت کامل", reply_markup=B.amenu())
                key = next((k for k in CATALOG if k in text), None)
                if key:
                    st["production_service_key"] = key
                    return await update.message.reply_text(
                        "🔧 {}\n📌 وضعیت: {}\n💰 قیمت: {:,} تومان".format(_label(B, key, "fa"), "باز" if _active(B, key) else "بسته", _price(B, key)),
                        reply_markup=B.kb([["🔄 باز/بسته"], ["✏️ متن فارسی", "✏️ English"], ["✏️ العربية", "💰 قیمت"], ["⬅️ بازگشت"]]),
                    )
            if mode == "service_action":
                key = st.get("production_service_key")
                if key:
                    if text == "🔄 باز/بسته":
                        new = "0" if _active(B, key) else "1"
                        B.db.set_setting("service_active_" + key, new)
                        return await update.message.reply_text("🟢 خدمت باز شد." if new == "1" else "🔴 خدمت بسته شد.", reply_markup=B.kb(_service_admin_rows(B)))
                    if text == "💰 قیمت":
                        st["production_admin_mode"] = "service_price"
                        return await update.message.reply_text("💰 قیمت جدید را فقط به تومان وارد کنید:", reply_markup=B.kb([["⬅️ بازگشت"]]))
                    lang = {"✏️ متن فارسی": "fa", "✏️ English": "en", "✏️ العربية": "ar"}.get(text)
                    if lang:
                        st["production_label_lang"] = lang
                        st["production_admin_mode"] = "service_label"
                        return await update.message.reply_text("✏️ متن جدید این بخش را ارسال کنید:", reply_markup=B.kb([["⬅️ بازگشت"]]))
            if mode == "service_label" and st.get("production_service_key"):
                key = st["production_service_key"]; lang = st.get("production_label_lang", "fa")
                B.db.set_setting("service_label_{}_{}".format(key, lang), text)
                st["production_admin_mode"] = "services"
                return await update.message.reply_text("✅ متن {} ذخیره شد.".format(lang), reply_markup=B.kb(_service_admin_rows(B)))
            if mode == "service_price" and st.get("production_service_key"):
                raw = _digits(text).replace(",", "").replace("٬", "").replace(" ", "").replace("تومان", "")
                if not raw.isdigit():
                    return await update.message.reply_text("❌ قیمت باید عدد باشد.")
                key = st["production_service_key"]; amount = int(raw)
                B.db.set_setting("service_price_" + key, amount)
                B.db.set_setting("price_" + key, amount)
                B.db.conn.execute("UPDATE services SET price=? WHERE key=?", (amount, key)); B.db.conn.commit()
                st["production_admin_mode"] = "services"
                return await update.message.reply_text("✅ قیمت به {:,} تومان تغییر کرد.".format(amount), reply_markup=B.kb(_service_admin_rows(B)))
        # Support is always available and fixed to the requested ID.
        if text in {"📞 تماس با ما", "📞 Contact us", "📞 اتصل بنا"}:
            return await update.message.reply_text("📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی به این آیدی پیام دهید:\n@Good_ok_2000", reply_markup=B.main(uid))
        return await old_router(update, context)
    B.router = router
    B._production_final_installed = True
    log.info("production final patch installed")
