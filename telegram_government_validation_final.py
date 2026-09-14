"""Final validation owner for the canonical Government v3 flow."""
import re
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters


def install(app, B):
    if getattr(B, "_gov_validation_final", False):
        return

    async def text(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "govv3_dob":
            return
        value = str(update.message.text or "").strip()
        value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", value):
            await update.message.reply_text(
                "❌ تاریخ تولد صحیح نیست.\n\n"
                "📅 لطفاً به شکل ۱۳۷۰/۰۱/۱۵ وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
            raise ApplicationHandlerStop
        st["gov_dob"] = value
        st["mode"] = "govv3_unique"
        await update.message.reply_text(
            "🆔 شناسه یکتای مشترک را وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-121)
    B._gov_validation_final = True
