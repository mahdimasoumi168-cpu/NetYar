"""Final hardening for the government-document conversational flow.

Owns the ambiguous text/media states before legacy government handlers. Card
and temporary-card use the same information flow and one document image;
residence booklet uses two images; passport uses three images. Household code
is required for both card types and must contain at least five digits.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))


def _cancel_markup():
    try:
        from telegram_government_documents_v3 import _cancel_markup as cm
        return cm()
    except Exception:
        return None


def install(app, B):
    if getattr(B, "_gov_flow_hardening_v4", False):
        return

    async def text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not msg.text:
            return
        st = B.S.setdefault(user.id, {})
        mode = str(st.get("mode") or "")
        if mode not in {
            "govv3_dob", "govv3_unique", "govv3_special", "govv3_family",
            "govv3_identity_number", "govv3_postal"
        }:
            return
        t = msg.text.strip()
        d = _digits(t)
        markup = _cancel_markup()
        kwargs = {"reply_markup": markup} if markup is not None else {}

        if mode == "govv3_dob":
            if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", d):
                await msg.reply_text("❌ تاریخ تولد نامعتبر است.\n\nمثال صحیح: 1385/05/12", **kwargs)
            else:
                st["gov_dob"] = d
                st["mode"] = "govv3_unique"
                await msg.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:", **kwargs)
            raise ApplicationHandlerStop

        if mode == "govv3_unique":
            if not re.fullmatch(r"9\d{9}", d):
                await msg.reply_text("❌ شناسه یکتا باید دقیقاً ۱۰ رقم و با ۹ شروع شود.", **kwargs)
            else:
                st["gov_unique"] = d
                st["mode"] = "govv3_special"
                await msg.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:", **kwargs)
            raise ApplicationHandlerStop

        if mode == "govv3_special":
            if not re.fullmatch(r"1\d{11}", d):
                await msg.reply_text("❌ شناسه اختصاصی باید دقیقاً ۱۲ رقم و با ۱ شروع شود.", **kwargs)
            else:
                st["gov_special"] = d
                typ = st.get("gov_doc_type")
                # Amayesh and temporary card have the same information flow.
                if typ in {"card", "temporary_card"}:
                    st["mode"] = "govv3_family"
                    await msg.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (حداقل ۵ رقم):", **kwargs)
                else:
                    st["mode"] = "govv3_identity_number"
                    prompt = {
                        "passport": "🛂 شماره گذرنامه مشترک را وارد کنید:",
                        "residence_booklet": "📗 شماره دفترچه اقامت مشترک را وارد کنید:",
                    }.get(typ, "🪪 شماره مدرک مشترک را وارد کنید:")
                    await msg.reply_text(prompt, **kwargs)
            raise ApplicationHandlerStop

        if mode == "govv3_family":
            if not re.fullmatch(r"\d{5,}", d):
                await msg.reply_text("❌ کد خانوار نامعتبر است. کد خانوار باید عددی و حداقل ۵ رقم باشد.", **kwargs)
            else:
                st["gov_family_code"] = d
                st["mode"] = "govv3_postal"
                await msg.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", **kwargs)
            raise ApplicationHandlerStop

        if mode == "govv3_identity_number":
            if not re.fullmatch(r"\d{3,}", d):
                await msg.reply_text("❌ شماره مدرک را صحیح وارد کنید.", **kwargs)
            else:
                st["gov_identity_number"] = d
                st["mode"] = "govv3_postal"
                await msg.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:", **kwargs)
            raise ApplicationHandlerStop

        if mode == "govv3_postal":
            if not re.fullmatch(r"\d{10}", d):
                await msg.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.", **kwargs)
            else:
                st["gov_postal"] = d
                typ = st.get("gov_doc_type")
                if typ == "passport":
                    st["mode"] = "govv3_passport_photo1"
                    await msg.reply_text("📸 ۱/۳ — عکس صفحه اول پاسپورت مشترک را ارسال کنید:", **kwargs)
                elif typ == "residence_booklet":
                    st["mode"] = "govv3_residence_photo1"
                    await msg.reply_text("📗 ۱/۲ — عکس اول دفترچه اقامت مشترک را ارسال کنید:", **kwargs)
                else:
                    # Both Amayesh and temporary card require exactly one card image.
                    st["mode"] = "govv3_card_photo"
                    await msg.reply_text("🪪 ۱/۱ — عکس کارت مشترک را ارسال کنید:", **kwargs)
            raise ApplicationHandlerStop

    async def media(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user:
            return
        st = B.S.setdefault(user.id, {})
        mode = str(st.get("mode") or "")
        if mode not in {
            "govv3_card_photo", "govv3_residence_photo1", "govv3_residence_photo2",
            "govv3_passport_photo1", "govv3_passport_photo2", "govv3_passport_photo3"
        }:
            return
        fid = ""
        if getattr(msg, "photo", None):
            fid = msg.photo[-1].file_id
        elif getattr(msg, "document", None):
            fid = msg.document.file_id
        if not fid:
            await msg.reply_text("❌ لطفاً عکس یا فایل مدرک را ارسال کنید.")
            raise ApplicationHandlerStop

        if mode == "govv3_card_photo":
            st["gov_card_photo"] = fid
            st["mode"] = "govv3_sim_optional"
            await msg.reply_text("📱 سند سیم‌کارت مشترک اختیاری است.\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:")
        elif mode == "govv3_residence_photo1":
            st["gov_residence_photo1"] = fid
            st["mode"] = "govv3_residence_photo2"
            await msg.reply_text("📗 ۲/۲ — عکس دوم دفترچه اقامت مشترک را ارسال کنید:")
        elif mode == "govv3_residence_photo2":
            st["gov_residence_photo2"] = fid
            st["mode"] = "govv3_sim_optional"
            await msg.reply_text("📱 سند سیم‌کارت مشترک اختیاری است.\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:")
        elif mode == "govv3_passport_photo1":
            st["gov_passport_photo1"] = fid
            st["mode"] = "govv3_passport_photo2"
            await msg.reply_text("📸 ۲/۳ — عکس صفحه تمدید پاسپورت را ارسال کنید:")
        elif mode == "govv3_passport_photo2":
            st["gov_passport_photo2"] = fid
            st["mode"] = "govv3_passport_photo3"
            await msg.reply_text("📸 ۳/۳ — عکس صفحه تمدید/روادید پاسپورت را ارسال کنید:")
        elif mode == "govv3_passport_photo3":
            st["gov_passport_photo3"] = fid
            st["mode"] = "govv3_sim_optional"
            await msg.reply_text("📱 سند سیم‌کارت مشترک اختیاری است.\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:")
        raise ApplicationHandlerStop

    # Run before all legacy information/document handlers.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-300000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, media), group=-300000)
    B._gov_flow_hardening_v4 = True
