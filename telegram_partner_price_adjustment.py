"""Admin shortcut for increasing/decreasing a selected partner's service price."""
import re
from telegram.ext import MessageHandler, filters


def install(app, B):
    if getattr(B, "_partner_price_adjustment_installed", False):
        return
    import partner_pricing as P
    import admin_control_v5 as A
    old_menu = A.menu

    def menu(bot):
        rows = old_menu(bot)
        # Avoid duplicate button if this extension is reloaded.
        if not any("📈 کاهش/افزایش قیمت همکار خاص" in str(row) for row in rows):
            rows = rows + [["📈 کاهش/افزایش قیمت همکار خاص"]]
        return rows

    A.menu = menu

    async def handler(update, context):
        uid = update.effective_user.id
        if not B.admin(uid):
            return
        text = (update.message.text or "").strip()
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")

        if text == "📈 کاهش/افزایش قیمت همکار خاص":
            st["mode"] = "ppa_partner"
            return await update.message.reply_text(
                "📈 کاهش/افزایش قیمت همکار خاص\n\n"
                "شناسه یا شماره تلفن همکار را ارسال کنید:"
            )

        if mode == "ppa_partner":
            partner = P._find_partner(B.db, text)
            if not partner:
                return await update.message.reply_text("❌ همکار پیدا نشد.")
            st["ppa_partner_id"] = int(partner["id"])
            st["mode"] = "ppa_service"
            services = "\n".join(
                f"• {r['key']} — {r['name']} — {int(r['price']):,} تومان"
                for r in P._services(B.db)
            )
            return await update.message.reply_text(
                f"👤 همکار: {partner['name'] or '-'} | 📱 {partner['phone']}\n\n"
                f"کلید خدمت را ارسال کنید:\n{services}"
            )

        if mode == "ppa_service":
            key = text.split("|")[0].strip()
            row = B.db.conn.execute(
                "SELECT key,name,price FROM services WHERE key=?", (key,)
            ).fetchone()
            if not row:
                return await update.message.reply_text("❌ کلید خدمت پیدا نشد.")
            current = B.db.conn.execute(
                "SELECT price FROM partner_service_prices WHERE partner_id=? AND service_key=?",
                (st["ppa_partner_id"], key),
            ).fetchone()
            st["ppa_service_key"] = key
            st["ppa_current"] = int(current["price"]) if current else int(row["price"])
            st["mode"] = "ppa_direction"
            return await update.message.reply_text(
                f"💰 {row['name']}\n"
                f"قیمت فعلی همکار: {st['ppa_current']:,} تومان\n\n"
                "نوع تغییر را انتخاب کنید:",
                reply_markup=B.kb([["➖ کاهش قیمت", "➕ افزایش قیمت"], [B.CANCEL]])
            )

        if mode == "ppa_direction":
            if text not in {"➖ کاهش قیمت", "➕ افزایش قیمت"}:
                return
            st["ppa_direction"] = "down" if text.startswith("➖") else "up"
            st["mode"] = "ppa_amount"
            return await update.message.reply_text("🔢 مبلغ تغییر را به تومان وارد کنید:")

        if mode == "ppa_amount":
            raw = re.sub(r"[٬,\s]", "", text)
            if not raw.isdigit():
                return await update.message.reply_text("❌ فقط عدد وارد کنید.")
            amount = int(raw)
            old_price = int(st["ppa_current"])
            new_price = old_price - amount if st["ppa_direction"] == "down" else old_price + amount
            if new_price < 0:
                return await update.message.reply_text("❌ قیمت نهایی نمی‌تواند منفی باشد.")
            B.db.conn.execute(
                "INSERT OR REPLACE INTO partner_service_prices VALUES(?,?,?,?)",
                (st["ppa_partner_id"], st["ppa_service_key"], new_price, P._now()),
            )
            B.db.conn.commit()
            st["mode"] = "v5"
            sign = "-" if st["ppa_direction"] == "down" else "+"
            return await update.message.reply_text(
                f"✅ قیمت همکار با موفقیت تغییر کرد.\n\n"
                f"قیمت قبلی: {old_price:,} تومان\n"
                f"تغییر: {sign}{amount:,} تومان\n"
                f"قیمت جدید: {new_price:,} تومان\n\n"
                "👤 این تغییر فقط برای همین همکار و همین خدمت اعمال شد.",
                reply_markup=A.menu(B),
            )

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler), group=-8)
    B._partner_price_adjustment_installed = True
