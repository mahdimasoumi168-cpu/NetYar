"""Final defensive owner for text information entry.

This layer handles the legacy aliases that can otherwise fall through to a
menu/fallback handler. It is intentionally narrow: it only consumes active
input states and never consumes ordinary menu text.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789")


def _digits(v):
    return str(v or "").translate(_DIGITS)


def _phone(v):
    s = _digits(v).strip()
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s if re.fullmatch(r"09\d{9}", s) else None


def install(app, B):
    if getattr(B, "_input_hardening_v3", False):
        return

    async def text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not msg.text:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        mode = str(st.get("mode") or "")
        value = msg.text.strip()

        # Legacy government aliases. Some older overlays use gov_phone while
        # the v2 flow uses govv2_phone. The latter is owned by the dedicated
        # v2 handler; these aliases are handled here so the number never falls
        # through to the generic router.
        if mode in {"gov_phone", "subscriber_phone", "mobile"}:
            phone = _phone(value)
            if not phone:
                await msg.reply_text(
                    "❌ شماره موبایل مشترک صحیح نیست.\n\n"
                    "شماره را به شکل 09xxxxxxxxx وارد کنید."
                )
            else:
                st["gov_phone"] = phone
                st["phone"] = phone
                st["mode"] = "gov_dob"
                await msg.reply_text(
                    "🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید:"
                )
            raise ApplicationHandlerStop

        # Partner login aliases. This prevents the phone/password step from
        # being swallowed by the normal menu router.
        if mode == "p_phone":
            phone = _phone(value)
            if not phone:
                await msg.reply_text(
                    "❌ شماره همراه همکار صحیح نیست.\n\n"
                    "شماره را به شکل 09xxxxxxxxx وارد کنید."
                )
                raise ApplicationHandlerStop
            try:
                partner = B.db.partner(phone)
            except Exception:
                partner = None
            if not partner:
                await msg.reply_text("❌ همکار با این شماره پیدا نشد.")
                raise ApplicationHandlerStop
            st["phone"] = phone
            st["mode"] = "p_pass"
            await msg.reply_text("🔐 رمز عبور همکار را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "p_pass":
            try:
                from core import check_password
                partner = B.db.partner(st.get("phone"))
                ok = bool(partner and check_password(value, partner["password_hash"]))
            except Exception:
                partner = None
                ok = False
            if not ok:
                await msg.reply_text("❌ شماره همراه یا رمز عبور نادرست است.")
                raise ApplicationHandlerStop
            st.update({
                "partner_id": partner["id"],
                "partner_active": True,
                "mode": None,
            })
            try:
                await B.partner(update, context)
            except Exception:
                await msg.reply_text(
                    "✅ ورود انجام شد.\n\n👥 پنل همکاران را انتخاب کنید.",
                    reply_markup=B.partner_kb(st.get("lang", "fa")),
                )
            raise ApplicationHandlerStop

        # Never intercept ordinary text or already-owned v2/admin states.
        return

    # Earlier than every legacy router, but after callback handlers. Only text
    # with an active state is consumed, so normal buttons remain untouched.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text),
        group=-300000,
    )
    B._input_hardening_v3 = True
