"""Deterministic Telegram admin pricing flow for partner services.

Owns the complete per-partner pricing conversation so legacy pricing handlers
cannot consume the same phone/service/price messages and emit false errors.
"""
import re
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

SERVICES = (
    ("government", "🏛 حل مشکل سامانه دولت من"),
    ("fida", "🪪 فیدای غیر حضوری"),
    ("sim_price_samantel", "📱 سیم کارت سامانتل"),
    ("sim_price_irancell", "📱 سیم کارت ایرانسل"),
    ("sim_price_rightel", "📱 سیم کارت رایتل"),
    ("tracking", "🔎 پیگیری کد"),
)

ENTRY_CALLBACKS = {"adm:partner_price_adjust", "adm:partner_prices_seq", "adm:partner_price_adjust_final"}
CANCELS = {"❌ انصراف", "لغو", "انصراف", "Cancel", "إلغاء"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _menu(B):
    try:
        import telegram_admin_plus as A
        return A._admin_menu()
    except Exception:
        return None


def _find_partner(B, text):
    raw = _digits(text).strip()
    raw = raw.replace("+98", "0").replace("0098", "0")
    conn = B.db.conn
    p = None
    if raw.isdigit():
        # Never call int() on a long non-ID value unless it is actually a
        # numeric candidate; SQL handles the comparison safely.
        p = conn.execute("SELECT * FROM partners WHERE id=? OR phone=? LIMIT 1", (int(raw), raw)).fetchone()
    if not p:
        p = conn.execute("SELECT * FROM partners WHERE phone=? LIMIT 1", (raw,)).fetchone()
    if not p and text.strip():
        p = conn.execute("SELECT * FROM partners WHERE name LIKE ? ORDER BY id LIMIT 1", (f"%{text.strip()}%",)).fetchone()
    return p


def _current(B, pid, key):
    row = B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?", (pid, key)).fetchone()
    if row:
        return int(row["price"] or 0)
    row = B.db.conn.execute("SELECT price FROM services WHERE key=?", (key,)).fetchone()
    return int(row["price"] or 0) if row else 0


def _save(B, pid, key, value):
    if value == 0:
        B.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?", (pid, key))
    else:
        B.db.conn.execute(
            "INSERT OR REPLACE INTO partner_service_prices(partner_id,service_key,price,updated_at) VALUES(?,?,?,?)",
            (pid, key, value, _now()),
        )
    B.db.conn.commit()


def _service_kb():
    rows = []
    for i, (_, label) in enumerate(SERVICES):
        rows.append([InlineKeyboardButton(label, callback_data=f"ppsvc:{i}")])
    rows.append([InlineKeyboardButton("⬅️ پنل مدیریت", callback_data="adm:menu"), InlineKeyboardButton("❌ انصراف", callback_data="ppcancel")])
    return InlineKeyboardMarkup(rows)


def install(app, B):
    if getattr(B, "_stable_partner_pricing", False):
        return

    B.db.conn.execute("""CREATE TABLE IF NOT EXISTS partner_service_prices(
        partner_id INTEGER NOT NULL,
        service_key TEXT NOT NULL,
        price INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(partner_id, service_key)
    )""")
    B.db.conn.commit()

    async def callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        data = str(q.data or "")
        if data in ENTRY_CALLBACKS:
            await q.answer()
            st = B.S.setdefault(q.from_user.id, {"admin": True})
            st.update({"mode": "sp_partner", "sp_service": None, "sp_partner_id": None})
            await q.message.reply_text("📋 قیمت‌گذاری تک‌تک خدمات همکار\n\n📱 شماره موبایل، شناسه یا نام همکار را ارسال کنید:")
            raise ApplicationHandlerStop
        if data.startswith("ppsvc:"):
            await q.answer()
            st = B.S.setdefault(q.from_user.id, {})
            if st.get("mode") != "sp_service" or not st.get("sp_partner_id"):
                await q.message.reply_text("❌ نشست قیمت‌گذاری منقضی شده است. دوباره قیمت‌گذاری را شروع کنید.", reply_markup=_menu(B))
                raise ApplicationHandlerStop
            try:
                idx = int(data.split(":", 1)[1])
                key, label = SERVICES[idx]
            except (ValueError, IndexError):
                await q.message.reply_text("❌ خدمت انتخاب‌شده معتبر نیست.", reply_markup=_service_kb())
                raise ApplicationHandlerStop
            st.update({"mode": "sp_price", "sp_service": key, "sp_service_label": label})
            current = _current(B, int(st["sp_partner_id"]), key)
            await q.message.reply_text(
                f"👤 همکار: {st.get('sp_partner_name', '-') }\n\n{label}\n💰 قیمت فعلی: {current:,} تومان\n\n"
                "💵 قیمت جدید را به تومان وارد کنید.\nبرای حذف قیمت اختصاصی و برگشت به قیمت عمومی: 0"
            )
            raise ApplicationHandlerStop
        if data == "ppcancel":
            await q.answer()
            st = B.S.setdefault(q.from_user.id, {})
            for k in ("sp_partner_id", "sp_partner_name", "sp_service", "sp_service_label"):
                st.pop(k, None)
            st["mode"] = None
            await q.message.reply_text("❌ قیمت‌گذاری لغو شد.", reply_markup=_menu(B))
            raise ApplicationHandlerStop

    async def text(update, context):
        if not update.message or not update.effective_user or not B.admin(update.effective_user.id):
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        text = (update.message.text or "").strip()
        if mode not in {"sp_partner", "sp_service", "sp_price"}:
            return
        if text in CANCELS:
            for k in ("sp_partner_id", "sp_partner_name", "sp_service", "sp_service_label"):
                st.pop(k, None)
            st["mode"] = None
            await update.message.reply_text("❌ قیمت‌گذاری لغو شد.", reply_markup=_menu(B))
            raise ApplicationHandlerStop
        if mode == "sp_partner":
            p = _find_partner(B, text)
            if not p:
                await update.message.reply_text("❌ همکار پیدا نشد. شماره موبایل، شناسه یا نام را دوباره وارد کنید.")
                raise ApplicationHandlerStop
            st.update({"mode": "sp_service", "sp_partner_id": int(p["id"]), "sp_partner_name": p["name"] or p["phone"]})
            await update.message.reply_text(
                f"👤 همکار انتخاب شد: {p['name'] or '-'}\n📱 {p['phone']}\n\nخدمت موردنظر را انتخاب کنید:",
                reply_markup=_service_kb(),
            )
            raise ApplicationHandlerStop
        if mode == "sp_price":
            raw = re.sub(r"[٬,\s]", "", _digits(text))
            if not raw.isdigit():
                await update.message.reply_text("❌ فقط عدد وارد کنید؛ مثال: 420000")
                raise ApplicationHandlerStop
            value = int(raw)
            if value < 0:
                await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد.")
                raise ApplicationHandlerStop
            key = st.get("sp_service")
            if not key or not st.get("sp_partner_id"):
                await update.message.reply_text("❌ نشست قیمت‌گذاری ناقص است. دوباره از پنل مدیریت شروع کنید.", reply_markup=_menu(B))
                st["mode"] = None
                raise ApplicationHandlerStop
            label = st.get("sp_service_label", key)
            _save(B, int(st["sp_partner_id"]), key, value)
            result = "🗑 قیمت اختصاصی حذف شد و قیمت عمومی فعال شد." if value == 0 else f"✅ {label}\nقیمت اختصاصی: {value:,} تومان"
            st["mode"] = "sp_service"
            await update.message.reply_text(result + "\n\nخدمت بعدی را انتخاب کنید:", reply_markup=_service_kb())
            raise ApplicationHandlerStop
        # sp_service should normally be entered through a button, not free text.
        await update.message.reply_text("لطفاً خدمت را از دکمه‌های زیر انتخاب کنید:", reply_markup=_service_kb())
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^(adm:partner_price_adjust|adm:partner_prices_seq|adm:partner_price_adjust_final|ppsvc:\d+|ppcancel)$"), group=-13000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-12999)
    B._stable_partner_pricing = True
