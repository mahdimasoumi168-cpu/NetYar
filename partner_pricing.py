"""Per-partner service pricing and admin controls."""
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

_ACTIVE_PARTNER = ContextVar("netyar_active_partner", default=None)


def _now():
    return datetime.now(timezone.utc).isoformat()


def ensure(db):
    db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
        partner_id INTEGER NOT NULL,
        service_key TEXT NOT NULL,
        price INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(partner_id, service_key)
    )""")
    db.conn.commit()


def price(db, service_key, partner_id=None, default=None):
    ensure(db)
    if partner_id:
        r = db.conn.execute(
            "SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",
            (partner_id, service_key),
        ).fetchone()
        if r:
            return int(r["price"])
    if default is not None:
        return int(default)
    r = db.conn.execute("SELECT price FROM services WHERE key=?", (service_key,)).fetchone()
    return int(r["price"] or 0) if r else 0


def _find_partner(db, value):
    v = str(value or "").strip()
    if v.isdigit():
        return db.conn.execute(
            "SELECT * FROM partners WHERE id=? OR phone=?", (int(v), v)
        ).fetchone()
    return db.conn.execute(
        "SELECT * FROM partners WHERE phone=? OR name LIKE ? ORDER BY id LIMIT 1",
        (v, f"%{v}%"),
    ).fetchone()


def _services(db):
    return db.conn.execute("SELECT key,name,price FROM services ORDER BY id").fetchall()


def _patch_setting(db):
    if getattr(db, "_partner_price_setting_patch", False):
        return
    old = db.setting

    def setting(key, default=""):
        pid = _ACTIVE_PARTNER.get()
        if pid and key.startswith("price_"):
            service = {
                "price_government": "government",
                "price_fida": "fida",
                "price_print_bw": "print_bw",
                "price_print_color": "print_color",
            }.get(key)
            if service:
                return str(price(db, service, pid, default))
        return old(key, default)

    db.setting = setting
    db._partner_price_setting_patch = True


def _admin_pricing_button():
    return InlineKeyboardButton("📈 کاهش/افزایش قیمت همکار خاص", callback_data="adm:partner_price_adjust")


def install_telegram(app, B):
    ensure(B.db)
    _patch_setting(B.db)

    # The production Telegram admin panel is telegram_admin_plus._admin_menu.
    # Do not patch the legacy admin_control_v5 menu: doing so makes the option
    # invisible in the actual production panel.
    import telegram_admin_plus as A
    old_admin_menu = A._admin_menu

    if not getattr(A, "_partner_price_menu_patched", False):
        def admin_menu_with_partner_price():
            markup = old_admin_menu()
            rows = [list(row) for row in markup.inline_keyboard]
            rows.insert(max(0, len(rows) - 1), [_admin_pricing_button()])
            return InlineKeyboardMarkup(rows)
        A._admin_menu = admin_menu_with_partner_price
        A._partner_price_menu_patched = True

    async def callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = q.data or ""
        if data != "adm:partner_price_adjust":
            return
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        st["mode"] = "pp_partner"
        st["pp_adjust"] = True
        return await q.message.reply_text(
            "📈 کاهش/افزایش قیمت برای همکار خاص\n\n"
            "شناسه یا شماره تلفن همکار را ارسال کنید:"
        )

    async def handler(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        if not B.admin(uid):
            return
        t = (update.message.text or "").strip()
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")

        # Backward-compatible text entry for the same feature.
        if t in {"🎁 قیمت ویژه همکاران", "📈 کاهش/افزایش قیمت همکار خاص"}:
            st["mode"] = "pp_partner"
            st["pp_adjust"] = t.startswith("📈")
            return await update.message.reply_text(
                "📈 کاهش/افزایش قیمت برای همکار خاص\n\n"
                "شناسه یا شماره تلفن همکار را ارسال کنید:"
            )

        if mode == "pp_partner":
            p = _find_partner(B.db, t)
            if not p:
                return await update.message.reply_text("❌ همکار پیدا نشد.")
            st["pp_partner_id"] = int(p["id"])
            st["mode"] = "pp_service"
            return await update.message.reply_text(
                "👤 همکار: {} | 📱 {}\n\nکلید خدمت را ارسال کنید:\n{}".format(
                    p["name"] or "-",
                    p["phone"],
                    "\n".join(
                        f"• {r['key']} — {r['name']} — {int(r['price']):,} تومان"
                        for r in _services(B.db)
                    ),
                )
            )

        if mode == "pp_service":
            key = t.split("|")[0].strip()
            r = B.db.conn.execute(
                "SELECT key,name,price FROM services WHERE key=?", (key,)
            ).fetchone()
            if not r:
                return await update.message.reply_text("❌ کلید خدمت پیدا نشد.")
            st["pp_service_key"] = key
            cur = B.db.conn.execute(
                "SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",
                (st["pp_partner_id"], key),
            ).fetchone()
            shown = int(cur["price"]) if cur else int(r["price"])
            st["pp_current_price"] = shown
            if st.get("pp_adjust"):
                st["mode"] = "pp_adjust_direction"
                return await update.message.reply_text(
                    f"💰 {r['name']}\nقیمت فعلی همکار: {shown:,} تومان\n\nنوع تغییر را انتخاب کنید:",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("➖ کاهش قیمت", callback_data="pp:down"),
                            InlineKeyboardButton("➕ افزایش قیمت", callback_data="pp:up"),
                        ],
                        [InlineKeyboardButton("⬅️ پنل مدیریت", callback_data="pp:back")],
                    ]),
                )
            st["mode"] = "pp_price"
            return await update.message.reply_text(
                f"💰 {r['name']}\nقیمت عمومی: {int(r['price']):,} تومان\n"
                f"قیمت فعلی همکار: {shown:,} تومان\n\n"
                "قیمت ویژه جدید را بفرستید.\nبرای حذف قیمت ویژه: 0"
            )

        if mode == "pp_adjust_value":
            raw = re.sub(r"[٬,\s]", "", t)
            if not raw.isdigit():
                return await update.message.reply_text("❌ فقط عدد وارد کنید.")
            amount = int(raw)
            current = int(st.get("pp_current_price", 0))
            direction = st.get("pp_adjust_direction")
            new = current - amount if direction == "down" else current + amount
            if new < 0:
                return await update.message.reply_text("❌ قیمت نهایی نمی‌تواند منفی باشد.")
            pid = st["pp_partner_id"]
            key = st["pp_service_key"]
            B.db.conn.execute(
                "INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",
                (pid, key, new, _now()),
            )
            B.db.conn.commit()
            st["mode"] = None
            return await update.message.reply_text(
                f"✅ قیمت همکار تغییر کرد.\n\n"
                f"قیمت قبلی: {current:,} تومان\n"
                f"تغییر: {'-' if direction == 'down' else '+'}{amount:,} تومان\n"
                f"قیمت جدید: {new:,} تومان\n\n"
                "👤 فقط برای همین همکار اعمال می‌شود.",
                reply_markup=A._admin_menu(),
            )

        if mode == "pp_price":
            raw = re.sub(r"[٬,\s]", "", t)
            if not raw.isdigit():
                return await update.message.reply_text("❌ فقط عدد وارد کنید.")
            pid = st["pp_partner_id"]
            key = st["pp_service_key"]
            v = int(raw)
            if v == 0:
                B.db.conn.execute(
                    "DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?",
                    (pid, key),
                )
                msg = "🗑 قیمت ویژه حذف شد و قیمت عمومی فعال شد."
            else:
                B.db.conn.execute(
                    "INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",
                    (pid, key, v, _now()),
                )
                msg = f"✅ قیمت ویژه {v:,} تومان ثبت شد."
            B.db.conn.commit()
            st["mode"] = None
            return await update.message.reply_text(
                msg + "\n👤 فقط برای همین همکار اعمال می‌شود.",
                reply_markup=A._admin_menu(),
            )

    async def price_callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = q.data or ""
        if data not in {"pp:down", "pp:up", "pp:back"}:
            return
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        if data == "pp:back":
            st["mode"] = None
            return await q.message.reply_text("🛠 پنل مدیریت", reply_markup=A._admin_menu())
        st["pp_adjust_direction"] = "down" if data == "pp:down" else "up"
        st["mode"] = "pp_adjust_value"
        return await q.message.reply_text("🔢 مبلغ تغییر را به تومان وارد کنید:")

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^adm:partner_price_adjust$"), group=-35)
    app.add_handler(CallbackQueryHandler(price_callback, pattern=r"^pp:(down|up|back)$"), group=-35)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-7)

    # Government media pricing is request-scoped by partner.
    import telegram_ux_billing as U
    if not getattr(U, "_partner_pricing_wrapped", False):
        old_media = U._gov_media

        async def priced_media(update, context):
            pid = B.S.get(update.effective_user.id, {}).get("partner_id")
            tok = _ACTIVE_PARTNER.set(pid)
            try:
                return await old_media(update, context)
            finally:
                _ACTIVE_PARTNER.reset(tok)

        U._gov_media = priced_media
        U._partner_pricing_wrapped = True


def install_rubika(R):
    ensure(R.db)
    _patch_setting(R.db)
    old_rows = R.admin_rows

    if not getattr(R, "_partner_price_admin_patched", False):
        def admin_rows():
            rows = list(old_rows())
            if not any(any(str(b[0]) == "19" for b in row) for row in rows):
                rows.append([("19", "📈 کاهش/افزایش قیمت همکار خاص")])
            return rows
        R.admin_rows = admin_rows
        R._partner_price_admin_patched = True

    old_admin = R.admin

    def admin(uid, chat, x):
        st = R.STATE.setdefault(str(uid), {})
        x = str(x).strip()
        step = st.get("step")
        if x in {"19", "📈 کاهش/افزایش قیمت همکار خاص"}:
            st["step"] = "pp_partner"
            st["pp_adjust"] = True
            return R.send(chat, "📈 کاهش/افزایش قیمت برای همکار خاص\n\nشناسه یا شماره تلفن همکار را ارسال کنید.", [[("0", "⬅️ مدیریت")]])
        if step == "pp_partner":
            p = _find_partner(R.db, x)
            if not p:
                return R.send(chat, "❌ همکار پیدا نشد.")
            st["pp_partner_id"] = int(p["id"])
            st["step"] = "pp_service"
            return R.send(chat, "👤 همکار: {} | 📱 {}\n\nکلید خدمت را ارسال کنید:\n{}".format(
                p["name"] or "-", p["phone"], "\n".join(
                    f"• {r['key']} — {r['name']} — {int(r['price']):,}" for r in _services(R.db)
                )))
        if step == "pp_service":
            key = x.split("|")[0].strip()
            r = R.db.conn.execute("SELECT key,name,price FROM services WHERE key=?", (key,)).fetchone()
            if not r:
                return R.send(chat, "❌ کلید خدمت پیدا نشد.")
            cur = R.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?", (st["pp_partner_id"], key)).fetchone()
            shown = int(cur["price"]) if cur else int(r["price"])
            st.update({"pp_service_key": key, "pp_current_price": shown, "step": "pp_adjust_direction"})
            return R.send(chat, f"💰 {r['name']}\nقیمت فعلی: {shown:,}\n\nنوع تغییر را انتخاب کنید:", [[("1", "➖ کاهش قیمت"), ("2", "➕ افزایش قیمت")], [("0", "⬅️ مدیریت")]])
        if step == "pp_adjust_direction" and x in {"1", "2", "➖ کاهش قیمت", "➕ افزایش قیمت"}:
            st["pp_adjust_direction"] = "down" if x in {"1", "➖ کاهش قیمت"} else "up"
            st["step"] = "pp_adjust_value"
            return R.send(chat, "🔢 مبلغ تغییر را به تومان وارد کنید:")
        if step == "pp_adjust_value":
            raw = re.sub(r"[٬,\s]", "", x)
            if not raw.isdigit():
                return R.send(chat, "❌ فقط عدد وارد کنید.")
            amount = int(raw)
            current = int(st["pp_current_price"])
            new = current - amount if st["pp_adjust_direction"] == "down" else current + amount
            if new < 0:
                return R.send(chat, "❌ قیمت نهایی نمی‌تواند منفی باشد.")
            R.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)", (st["pp_partner_id"], st["pp_service_key"], new, _now()))
            R.db.conn.commit()
            st["step"] = "admin"
            return R.send(chat, f"✅ قیمت جدید همکار: {new:,}\n👤 فقط برای همین همکار اعمال شد.", R.admin_rows())
        return old_admin(uid, chat, x)

    R.admin = admin
    old_process = R.process

    def process(update):
        uid = str(update.get("sender_id") or update.get("user_id") or update.get("chat_id") or "") if isinstance(update, dict) else ""
        pid = R.STATE.get(uid, {}).get("partner_id")
        tok = _ACTIVE_PARTNER.set(pid)
        try:
            return old_process(update)
        finally:
            _ACTIVE_PARTNER.reset(tok)

    R.process = process
