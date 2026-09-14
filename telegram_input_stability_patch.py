"""Final input-collection guard for Telegram.

Keeps text-entry state deterministic, especially phone-number steps in partner,
service and admin flows.  Installed as the last runtime patch so it wins over
legacy wrappers without changing the existing service implementations.
"""
import re
import logging

log = logging.getLogger("netyar.telegram_input_stability")

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _digits(value):
    return str(value or "").translate(_DIGITS)


def _phone(value):
    s = _digits(value).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif len(s) == 10 and s.startswith("9"):
        s = "0" + s
    return s if re.fullmatch(r"09\d{9}", s) else None


class _MessageProxy:
    def __init__(self, message, text):
        self._message = message
        self.text = text
    def __getattr__(self, name):
        return getattr(self._message, name)


class _UpdateProxy:
    def __init__(self, update, text):
        self._update = update
        self.message = _MessageProxy(update.message, text)
    def __getattr__(self, name):
        return getattr(self._update, name)


def install():
    import bot as B

    if getattr(B, "_telegram_input_stability_installed", False):
        return

    old_service_text = getattr(B, "service_text", None)
    old_ptext = getattr(B, "ptext", None)
    old_admin_text = getattr(B, "admin_text", None)

    async def service_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        text = str(getattr(update.message, "text", "") or "").strip()

        # This step previously reached conflicting legacy handlers. Handle it
        # here, once, and always advance to the next deterministic state.
        if mode == "gov_phone":
            phone = _phone(text)
            if not phone:
                return await update.message.reply_text(
                    B.L(uid,
                        "❌ شماره موبایل مشترک صحیح نیست.\nمثال: 09123456789",
                        "❌ Invalid customer mobile number.\nExample: 09123456789",
                        "❌ رقم هاتف العميل غير صحيح.\nمثال: 09123456789"),
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st["gov_phone"] = phone
            st["phone"] = phone
            st["mode"] = "gov_dob"
            return await update.message.reply_text(
                B.L(uid,
                    "🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید:",
                    "🎂 Enter the customer's birth date as 1356/01/01:",
                    "🎂 أدخل تاريخ ميلاد العميل بالشكل 1356/01/01:"),
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )

        # Normalize phone input for every known service phone state before the
        # underlying handler sees it. This fixes Persian/Arabic digits and +98.
        phone_modes = {
            "fida_phone", "sim_phone", "sim2_phone", "subscriber_phone",
            "mobile", "partner_phone", "power_add_phone", "admin_partner_phone",
            "admin_phone", "contact_phone",
        }
        if mode in phone_modes and old_service_text:
            phone = _phone(text)
            if not phone:
                return await update.message.reply_text(
                    "❌ شماره موبایل معتبر نیست. لطفاً شماره را به شکل 09xxxxxxxxx وارد کنید.",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            return await old_service_text(_UpdateProxy(update, phone), context)

        if old_service_text:
            return await old_service_text(update, context)
        return None

    async def ptext(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        text = str(getattr(update.message, "text", "") or "").strip()
        if mode == "p_phone" and old_ptext:
            phone = _phone(text)
            if not phone:
                return await update.message.reply_text(
                    "❌ شماره موبایل همکار صحیح نیست.\nمثال: 09123456789",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            return await old_ptext(_UpdateProxy(update, phone), context)
        if old_ptext:
            return await old_ptext(update, context)
        return None

    async def admin_text(update, context):
        if not old_admin_text:
            return None
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode") or st.get("admin_plus_mode")
        text = str(getattr(update.message, "text", "") or "").strip()
        phone_modes = {"power_add_phone", "admin_partner_phone", "admin_phone", "contact_phone"}
        if mode in phone_modes:
            phone = _phone(text)
            if not phone:
                return await update.message.reply_text(
                    "❌ شماره موبایل معتبر نیست. لطفاً شماره را به شکل 09xxxxxxxxx وارد کنید.",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            return await old_admin_text(_UpdateProxy(update, phone), context)
        return await old_admin_text(update, context)

    if old_service_text:
        B.service_text = service_text
    if old_ptext:
        B.ptext = ptext
    if old_admin_text:
        B.admin_text = admin_text

    B._telegram_input_stability_installed = True
    log.info("Telegram input stability patch installed")
