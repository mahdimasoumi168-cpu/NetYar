"""Reliable Telegram partner-panel login flow and robust phone normalization."""
import re
import logging
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram_partner_login_fix")


def normalize_phone(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[^0-9]+", "", s)
    if s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98"):
        s = "0" + s[2:]
    return s


def _phone_variants(value):
    p = normalize_phone(value)
    if not p:
        return set()
    variants = {p}
    if p.startswith("0") and len(p) == 11:
        variants.update({p[1:], "98" + p[1:], "+98" + p[1:], "0098" + p[1:]})
    elif p.startswith("98") and len(p) == 12:
        local = "0" + p[2:]
        variants.update({local, p, "+" + p, "00" + p})
    return variants


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
        if not re.fullmatch(r"09\d{9}", normalized):
            return None
        # First use the canonical DB lookup.
        try:
            row = original_partner(normalized)
            if row:
                return row
        except Exception:
            log.exception("canonical partner lookup failed")
        # Then compare normalized values against every active partner. This
        # handles legacy records stored as +98..., 0098..., Persian digits,
        # or with spaces/dashes without requiring migration of existing rows.
        try:
            rows = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
            for candidate in rows:
                stored = candidate["phone"] if "phone" in candidate.keys() else ""
                if normalize_phone(stored) == normalized:
                    return candidate
                if _phone_variants(stored) & _phone_variants(normalized):
                    return candidate
        except Exception:
            log.exception("partner normalized lookup failed")
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
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                await update.message.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 شماره موبایل اختصاصی همکار را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            partner = partner_fixed(phone)
            if not partner:
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                await update.message.reply_text("❌ این شماره به همکار فعال اختصاص ندارد.\n\n📱 شماره را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            st["partner_phone"] = phone
            st["phone"] = phone
            st["partner_id"] = partner["id"] if "id" in partner.keys() else None
            st["pending_partner_id"] = st["partner_id"]
            st["mode"] = "p_pass"; st["step"] = "partner_pass"
            await update.message.reply_text("🔐 رمز عبور پنل همکاران را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "p_pass" or step == "partner_pass":
            phone = normalize_phone(st.get("partner_phone") or st.get("phone"))
            partner = partner_fixed(phone) if phone else None
            ok = False
            try:
                ok = bool(partner and check_password(text, partner["password_hash"]))
            except Exception:
                log.exception("partner password verification failed")
            if not ok:
                st["mode"] = "p_pass"; st["step"] = "partner_pass"
                await update.message.reply_text("❌ رمز عبور نادرست است.\n\n🔐 رمز عبور همکار را دوباره وارد کنید:")
                raise ApplicationHandlerStop

            # Outside 07:00-19:00, partner access is available only when the
            # night switch is enabled AND this exact partner is whitelisted.
            try:
                from telegram_offhours_partner_gate_v2 import _clock_is_open, night_shift_enabled
                if not _clock_is_open(B) and not bool(B.admin(uid)):
                    if not night_shift_enabled(B):
                        st["mode"] = "p_phone"; st["step"] = "partner_phone"
                        await update.message.reply_text("🌙 شیفت شب در حال حاضر توسط مدیریت بسته است.\n\n🔄 بعداً دوباره تلاش کنید.")
                        raise ApplicationHandlerStop
                    pid = partner["id"] if "id" in partner.keys() else None
                    allowed = bool(pid) and str(B.db.setting("night_worker:"+str(pid),"0") or "0") == "1"
                    if not allowed:
                        st["mode"] = "p_phone"; st["step"] = "partner_phone"
                        for key in ("partner_id","pending_partner_id","partner_phone"):
                            st.pop(key,None)
                        await update.message.reply_text("❌ این حساب برای شیفت شب توسط مدیریت فعال نشده است.\n\n📞 برای فعال‌سازی با مدیریت تماس بگیرید.")
                        raise ApplicationHandlerStop
            except ApplicationHandlerStop:
                raise
            except Exception:
                log.exception("night-worker authorization check failed")
                await update.message.reply_text("❌ بررسی دسترسی شیفت شب انجام نشد. دوباره تلاش کنید.")
                raise ApplicationHandlerStop

            st["partner"] = phone
            st["partner_phone"] = phone
            st["partner_id"] = partner["id"] if "id" in partner.keys() else None
            st["partner_active"] = True
            st["partner_logged_out"] = False
            st["mode"] = "partner"; st["step"] = "partner"
            try:
                B.db.set_setting(f"partner_chat_{phone}", str(uid))
                if st.get("partner_id"):
                    B.db.set_setting(f"partner_chat_{st['partner_id']}", str(uid))
            except Exception:
                log.exception("partner chat mapping save failed")
            balance = int(partner["balance"] or 0)
            try:
                markup = B.partner_kb(st.get("lang", "fa"))
            except Exception:
                markup = None
            kwargs = {"reply_markup": markup} if markup is not None else {}
            await update.message.reply_text(
                f"👥 پنل همکاران\n👤 {partner['name'] or '-'}\n📱 {phone}\n💰 اعتبار قابل استفاده: {balance:,} تومان\n\nگزینه موردنظر را انتخاب کنید:",
                **kwargs,
            )
            raise ApplicationHandlerStop

        if mode == "partner" and text == "🚪 خروج از پنل":
            for key in ("partner", "partner_id", "partner_phone", "pending_partner_id"):
                st.pop(key, None)
            st["mode"] = None; st["step"] = None
            await update.message.reply_text("✅ از پنل همکاران خارج شدید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partner_login), group=-2000002)
    B._telegram_partner_login_fix_installed = True
    log.info("Telegram partner login fix installed")
