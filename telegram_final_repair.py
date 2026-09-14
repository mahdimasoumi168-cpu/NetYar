"""Final Telegram routing repair.

Runs before legacy catch-all handlers so admin-menu entry and partner login
inputs cannot be swallowed by older UI layers. The canonical /start handler
remains owned by telegram_runtime_clean to keep one welcome flow only.
"""
import logging
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.final_repair")


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _phone(v):
    s = re.sub(r"[^0-9]+", "", _digits(v))
    if s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98"):
        s = "0" + s[2:]
    return s


def install(app, B):
    if getattr(B, "_final_repair_installed", False):
        return

    async def admin_entry(update, context):
        if not update.effective_user or not update.message or not B.admin(update.effective_user.id):
            return
        text = (update.message.text or "").strip()
        if text not in {"🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات"}:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        st["admin"] = True
        st["admin_mode"] = None
        st["admin_plus_mode"] = None
        try:
            markup = B.amenu()
        except Exception:
            from telegram_admin_plus import _admin_menu
            markup = _admin_menu()
        await update.message.reply_text(
            "🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",
            reply_markup=markup,
        )
        raise ApplicationHandlerStop

    async def partner_entry(update, context):
        if not update.effective_user or not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        step = st.get("step")
        text = (update.message.text or "").strip()
        if mode not in {"p_phone", "p_pass"} and step not in {"partner_phone", "partner_pass"}:
            return
        if not text:
            return

        if mode == "p_phone" or step == "partner_phone":
            phone = _phone(text)
            if not re.fullmatch(r"09\d{9}", phone):
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                await update.message.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 شماره موبایل اختصاصی همکار را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            partner = B.db.partner(phone)
            if not partner:
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                await update.message.reply_text("❌ این شماره به همکار فعال اختصاص ندارد.\n\n📱 شماره را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            st.update(partner_phone=phone, phone=phone, partner_id=partner["id"], pending_partner_id=partner["id"], mode="p_pass", step="partner_pass")
            await update.message.reply_text("🔐 رمز عبور پنل همکاران را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "p_pass" or step == "partner_pass":
            phone = _phone(st.get("partner_phone") or st.get("phone"))
            partner = B.db.partner(phone) if phone else None
            ok = False
            try:
                from core import check_password
                ok = bool(partner and check_password(text, partner["password_hash"]))
            except Exception:
                log.exception("partner password verification failed")
            if not ok:
                st["mode"] = "p_pass"; st["step"] = "partner_pass"
                await update.message.reply_text("❌ رمز عبور نادرست است.\n\n🔐 رمز عبور پنل همکاران را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            st.update(partner=phone, partner_phone=phone, partner_id=partner["id"], partner_active=True, partner_logged_out=False, mode="partner", step="partner")
            try:
                B.db.set_setting(f"partner_chat_{phone}", str(uid))
                B.db.set_setting(f"partner_chat_{partner['id']}", str(uid))
            except Exception:
                log.exception("partner chat mapping save failed")
            balance = int(partner["balance"] or 0)
            try:
                markup = B.partner_kb(st.get("lang", "fa"))
            except Exception:
                markup = None
            await update.message.reply_text(
                f"👥 پنل همکاران\n👤 {partner['name'] or '-'}\n📱 {phone}\n💰 اعتبار قابل استفاده: {balance:,} تومان\n\nگزینه موردنظر را انتخاب کنید:",
                reply_markup=markup,
            )
            raise ApplicationHandlerStop

    # Do not register another /start handler here. The canonical runtime owns
    # /start and the multilingual welcome text; duplicate /start handlers were
    # causing the welcome message to change and sometimes duplicate.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_entry), group=-999999)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partner_entry), group=-999998)
    B._final_repair_installed = True
    log.info("final Telegram routing repair installed")
