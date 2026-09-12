"""Reliable Telegram partner-panel login flow and phone normalization."""
import re
import logging
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram_partner_login_fix")


def normalize_phone(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def install(app=None, B=None):
    if B is None:
        import bot as B
    if getattr(B, "_telegram_partner_login_fix_installed", False):
        return
    if app is None:
        return

    from core import check_password
    original_partner = B.db.partner

    def partner_fixed(phone):
        normalized = normalize_phone(phone)
        row = original_partner(normalized)
        if row:
            return row
        if not re.fullmatch(r"09\d{9}", normalized):
            return None
        try:
            rows = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
            for candidate in rows:
                if normalize_phone(candidate["phone"]) == normalized:
                    return candidate
        except Exception:
            log.exception("partner fallback lookup failed")
        return None

    B.db.partner = partner_fixed
    B.db.get_partner = partner_fixed

    async def partner_login(update, context):
        if not update.effective_user or not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        step = st.get("step")
        text = (update.message.text or "").strip()
        if not text:
            return

        if mode == "p_phone" or step == "partner_phone":
            phone = normalize_phone(text)
            if not re.fullmatch(r"09\d{9}", phone):
                await update.message.reply_text("❌ شماره همراه را صحیح وارد کنید.")
                raise ApplicationHandlerStop
            partner = partner_fixed(phone)
            if not partner:
                await update.message.reply_text("❌ همکار پیدا نشد. شماره همراه را دوباره وارد کنید.")
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                raise ApplicationHandlerStop
            st["partner_phone"] = phone
            st["mode"] = "p_pass"; st["step"] = "partner_pass"
            await update.message.reply_text("🔐 رمز عبور همکار را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "p_pass" or step == "partner_pass":
            phone = normalize_phone(st.get("partner_phone"))
            partner = partner_fixed(phone) if phone else None
            ok = False
            try:
                ok = bool(partner and check_password(text, partner["password_hash"]))
            except Exception:
                log.exception("partner password verification failed")
            if not ok:
                st["mode"] = "p_pass"; st["step"] = "partner_pass"
                await update.message.reply_text("❌ شماره همراه یا رمز عبور نادرست است.\n\n🔐 رمز عبور را دوباره وارد کنید:")
                raise ApplicationHandlerStop

            st["partner"] = phone
            st["partner_id"] = partner["id"] if "id" in partner.keys() else None
            st["mode"] = "partner"; st["step"] = "partner"
            try:
                B.db.set_setting(f"partner_chat_{phone}", str(uid))
                if st.get("partner_id"):
                    B.db.set_setting(f"partner_chat_{st['partner_id']}", str(uid))
            except Exception:
                log.exception("partner chat mapping save failed")
            balance = int(partner["balance"] or 0)
            markup = B.kb([
                ["➕ شارژ حساب", "🔎 پیگیری کد"],
                ["📋 سوابق", "💰 موجودی"],
                ["🏛 حل مشکل سامانه دولت من"],
                ["✉️ تیکت به مدیریت"],
                ["🚪 خروج از پنل"],
            ])
            await update.message.reply_text(f"👥 پنل همکار\n📱 {phone}\n💰 موجودی اعتبار: {balance:,} تومان\n\nگزینه موردنظر را انتخاب کنید:", reply_markup=markup)
            raise ApplicationHandlerStop

        if mode == "partner" and text == "🚪 خروج از پنل":
            for key in ("partner", "partner_id", "partner_phone"):
                st.pop(key, None)
            st["mode"] = None; st["step"] = None
            await update.message.reply_text("✅ از پنل همکاران خارج شدید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partner_login), group=-90)
    B._telegram_partner_login_fix_installed = True
    log.info("Telegram partner login fix installed")
