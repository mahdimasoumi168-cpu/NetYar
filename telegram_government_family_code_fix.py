"""Government document family-code correction.

For both Amayesh card and temporary card, the next field after special ID is
family code. This overlay owns only that transition and lets the existing
runtime flow handle the following steps.
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def install(app, B):
    if getattr(B, "_gov_family_code_fix", False):
        return

    async def text(update, context):
        if not update.message:
            return
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        if mode != "govv2_special":
            return
        typ = st.get("gov_doc_type")
        if typ not in {"card", "temporary_card"}:
            return
        d = _digits((update.message.text or "").strip())
        cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="govv2:cancel")]])
        if not d or not d.isdigit() or len(d) < 1:
            await update.message.reply_text("❌ کد خانوار را صحیح وارد کنید.", reply_markup=cancel)
            raise ApplicationHandlerStop
        st["gov_special"] = d if len(d) == 12 else st.get("gov_special")
        if len(d) != 12:
            await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم باشد.", reply_markup=cancel)
            raise ApplicationHandlerStop
        st["mode"] = "govv2_family"
        await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید:", reply_markup=cancel)
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-12000)
    B._gov_family_code_fix = True
