"""Highest-priority Telegram fixes for active phone input and partner logout.

This layer is intentionally installed before legacy routers so active input cannot
be swallowed by a generic menu/fallback handler.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop


def _norm(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def install(app, B):
    if getattr(B, "_critical_input_logout_fix", False):
        return

    async def critical(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not getattr(msg, "text", None):
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        text = str(msg.text or "").strip()
        mode = str(st.get("mode") or "")

        # Government-service phone input: consume it before every legacy router.
        if mode in {"govv2_phone", "gov_phone", "government_phone", "gov_phone_input"} or (
            st.get("gov_doc_type") and not st.get("gov_phone") and mode.startswith("govv2_")
        ):
            phone = _norm(text)
            if not re.fullmatch(r"09\d{9}", phone):
                await msg.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.\n\n📱 لطفاً شماره موبایل مشترک را دوباره وارد کنید:")
            else:
                st["gov_phone"] = phone
                st["mode"] = "govv2_dob"
                await msg.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        # Permanent partner logout: consume it before generic partner/menu routers.
        if mode == "partner_exit_choice" and text in {
            "🔒 خروج دائمی", "🔒 Permanent logout", "🔒 تسجيل الخروج الدائم"
        }:
            lang = st.get("lang", "fa")
            status = st.get("status", "foreign")
            B.S[uid] = {
                "lang": lang,
                "status": status,
                "citizenship": status,
                "partner_logged_out": True,
            }
            await msg.reply_text(
                "🔒 خروج از پنل با موفقیت انجام شد.\n\n"
                "برای ورود دوباره، خودتان دکمه «👥 پنل همکاران» را انتخاب کنید.",
                reply_markup=B.main(uid),
            )
            raise ApplicationHandlerStop

        # Temporary logout is also handled here so it cannot hit a generic router.
        if mode == "partner_exit_choice" and text in {
            "⏸ خروج موقت", "⏸ Temporary logout", "⏸ تسجيل الخروج المؤقت"
        }:
            st["mode"] = None
            st["partner_logged_out"] = True
            st.pop("partner_active", None)
            st.pop("partner_id", None)
            await msg.reply_text(
                "⏸ خروج موقت انجام شد.\n\nبرای ورود دوباره، «👥 پنل همکاران» را انتخاب کنید.",
                reply_markup=B.main(uid),
            )
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, critical), group=-2000000)
    B._critical_input_logout_fix = True
