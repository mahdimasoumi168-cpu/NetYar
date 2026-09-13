"""Final Telegram business/stability overlay.
Loaded after all legacy feature layers. It only adds missing partner menu
entries, corrects temporary-card government data collection, and provides a
simple per-partner/per-service exact-price workflow. It does not touch /data.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def install(app, B):
    # Partner home: expose FIDA + SIM without replacing the canonical callback UI.
    old_partner_kb = B.partner_kb
    if not getattr(B, "_final_partner_menu", False):
        def partner_kb(lang="fa"):
            try:
                rows = [list(row) for row in old_partner_kb(lang).inline_keyboard]
                labels = {str(getattr(b, "text", "")) for row in rows for b in row}
                if "🪪 فیدای غیر حضوری" not in labels:
                    rows.insert(min(2, len(rows)), [InlineKeyboardButton("🪪 فیدای غیر حضوری", callback_data="__placeholder_fida")])
                if "📱 خدمات سیم کارت" not in labels:
                    rows.insert(min(3, len(rows)), [InlineKeyboardButton("📱 خدمات سیم کارت", callback_data="__placeholder_sim")])
                return InlineKeyboardMarkup(rows)
            except Exception:
                return old_partner_kb(lang)
        B.partner_kb = partner_kb
        B._final_partner_menu = True

    async def partner_service_cb(update, context):
        q = update.callback_query
        if not q or q.data not in {"__placeholder_fida", "__placeholder_sim"}:
            return
        await q.answer()
        fn = getattr(B, "fida", None) if q.data == "__placeholder_fida" else getattr(B, "sim_start", None)
        if fn:
            result = fn(update, context)
            if hasattr(result, "__await__"):
                return await result
        return await q.message.reply_text("❌ این خدمت در حال حاضر در دسترس نیست.", reply_markup=B.partner_kb("fa"))

    app.add_handler(CallbackQueryHandler(partner_service_cb, pattern=r"^__(placeholder_fida|placeholder_sim)$"), group=-9000)

    # Temporary card: request family code, never temporary-card number.
    async def temp_cb(update, context):
        q = update.callback_query
        if not q or q.data != "govv2:temporary":
            return
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        st["gov_doc_type"] = "temporary_card"
        st["mode"] = "govv2_family_temp"
        return await q.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]]))

    async def temp_text(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "govv2_family_temp":
            return
        d = _digits(update.message.text).strip()
        if not d.isdigit():
            return await update.message.reply_text("❌ کد خانوار باید فقط عدد باشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]]))
        st["gov_family_code"] = d
        st["mode"] = "govv2_postal"
        await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]]))
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(temp_cb, pattern=r"^govv2:temporary$"), group=-8000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, temp_text), group=-8000)

    # Exact per-partner/per-service price workflow.
    services = [
        ("fida", "🪪 فیدای غیر حضوری"),
        ("government", "🏛 حل مشکل دولت من"),
        ("sim_card", "📱 سیم کارت"),
        ("print_bw", "🖨 چاپ سیاه‌وسفید"),
        ("print_color", "🌈 چاپ رنگی"),
    ]

    async def price_entry(update, context):
        q = update.callback_query
        if not q or q.data != "adm:partner_price_adjust" or not B.admin(q.from_user.id):
            return
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        st["mode"] = "final_pp_partner"
        return await q.message.reply_text("📈 قیمت ویژه همکار\n\nشناسه، شماره موبایل یا نام همکار را ارسال کنید:")

    async def price_text(update, context):
        if not update.message or not B.admin(update.effective_user.id):
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        t = (update.message.text or "").strip()
        if mode == "final_pp_partner":
            v = t
            row = B.db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=? OR name=? LIMIT 1", (int(v), v, v)).fetchone() if v.isdigit() else B.db.conn.execute("SELECT * FROM partners WHERE phone=? OR name=? LIMIT 1", (v, v)).fetchone()
            if not row:
                return await update.message.reply_text("❌ همکار پیدا نشد.")
            st["final_pp_pid"] = int(row["id"])
            st["mode"] = "final_pp_service"
            return await update.message.reply_text(f"👤 همکار: {row['name']}\n\nخدمت موردنظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(n, callback_data=f"fpp:service:{k}")] for k, n in services] + [[InlineKeyboardButton("⬅️ پنل مدیریت", callback_data="fpp:back")]]))
        if mode == "final_pp_amount":
            raw = re.sub(r"[٬,\s]", "", _digits(t))
            if not raw.isdigit():
                return await update.message.reply_text("❌ فقط عدد وارد کنید.")
            amount = int(raw)
            pid = int(st["final_pp_pid"])
            key = st["final_pp_key"]
            if amount == 0:
                B.db.conn.execute("DELETE FROM partner_service_prices WHERE partner_id=? AND service_key=?", (pid, key))
                msg = "🗑 قیمت ویژه حذف شد؛ قیمت عمومی فعال شد."
            else:
                B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)", (pid, key, amount, B.now()))
                msg = f"✅ قیمت {amount:,} تومان برای این همکار ثبت شد."
            B.db.conn.commit()
            st["mode"] = "final_pp_service"
            return await update.message.reply_text(msg + "\n\nخدمت بعدی را انتخاب کنید یا بازگشت بزنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(n, callback_data=f"fpp:service:{k}")] for k, n in services] + [[InlineKeyboardButton("⬅️ پنل مدیریت", callback_data="fpp:back")]]))

    async def price_cb(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        d = str(q.data or "")
        if d == "fpp:back":
            await q.answer()
            B.S.setdefault(q.from_user.id, {})["mode"] = None
            import telegram_admin_plus as A
            return await q.message.reply_text("🛠 پنل مدیریت", reply_markup=A._admin_menu())
        if not d.startswith("fpp:service:"):
            return
        await q.answer()
        key = d.split(":", 2)[2]
        st = B.S.setdefault(q.from_user.id, {})
        pid = int(st.get("final_pp_pid", 0))
        r = B.db.conn.execute("SELECT name,price FROM services WHERE key=?", (key,)).fetchone()
        if not r:
            return await q.message.reply_text("❌ خدمت پیدا نشد.")
        cur = B.db.conn.execute("SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?", (pid, key)).fetchone()
        current = int(cur["price"]) if cur else int(r["price"] or 0)
        st.update(mode="final_pp_amount", final_pp_key=key, final_pp_current=current)
        return await q.message.reply_text(f"💰 {r['name']}\nقیمت فعلی این همکار: {current:,} تومان\n\nقیمت جدید را وارد کنید.\nاگر ۰ بفرستید قیمت ویژه حذف می‌شود.")

    app.add_handler(CallbackQueryHandler(price_entry, pattern=r"^adm:partner_price_adjust$"), group=-8500)
    app.add_handler(CallbackQueryHandler(price_cb, pattern=r"^fpp:(service:.+|back)$"), group=-8500)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, price_text), group=-8500)
    B._final_stability_overlay = True
