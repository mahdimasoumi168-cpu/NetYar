"""Production v2 stability layer.

Keeps legacy handlers intact while fixing the remaining shared UX/state issues
for Telegram and Rubika. Idempotent: safe to load once at the end of runtime.
"""
import logging
import re

log = logging.getLogger("netyar.production_v2")

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
CANCEL = "❌ انصراف"
RESTART = "🔄 شروع مجدد"


def norm_digits(value):
    return str(value or "").translate(FA_DIGITS)


def norm_phone(value):
    s = norm_digits(value).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s if re.fullmatch(r"09\d{9}", s) else None


def _main_rows(B, uid):
    rows = [
        ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
        ["🏛 حل مشکل ورود اتباع دولت من", "🎫 پیگیری"],
        ["📱 خدمات سیم کارت", "📝 آزمون غربالگری"],
        ["💰 کیف پول من", "📞 تماس با ما"],
        ["📝 ثبت شکایت مشتریان", "👥 پنل همکاران"],
    ]
    if B.admin(uid):
        rows.append(["🔵 🛠 پنل مدیریت بات"])
    rows.append([RESTART])
    return B.kb(rows)


def _partner_rows(B):
    return B.kb([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        ["🎫 درخواست‌های من", "🔎 پیگیری کد"],
        ["📋 سوابق", "💰 موجودی"],
        ["✉️ ارسال تیکت به مدیریت"],
        ["🚪 خروج از پنل"],
        [RESTART],
    ])


def _safe_service_phone(st):
    # Accept the service's expected phone state without treating the prompt
    # itself as an invalid phone. Empty text is never validated as user input.
    for key in ("gov_phone", "phone", "mobile", "subscriber_phone"):
        if key in st:
            return key
    return "gov_phone"


def install():
    import bot as B

    if getattr(B, "_production_v2_installed", False):
        return

    # ---------- Telegram ----------
    old_main = B.main
    def stable_main(uid):
        return _main_rows(B, uid)
    B.main = stable_main

    old_partner_kb = B.partner_kb
    def stable_partner_kb(lang="fa"):
        return _partner_rows(B)
    B.partner_kb = stable_partner_kb

    old_cancel = B.cancel
    async def stable_cancel(update, context):
        uid = update.effective_user.id
        old = dict(B.S.get(uid, {}))
        lang = old.get("lang", "fa")
        partner_id = old.get("partner_id")
        # Keep only durable identity/context. Never carry an old mode into the
        # new menu; this is the root cause of many post-cancel dead buttons.
        B.S[uid] = {"lang": lang}
        if partner_id:
            B.S[uid].update({"partner_id": partner_id, "partner_active": True})
        return await update.message.reply_text(
            "❌ عملیات لغو شد.\n\nلطفاً از منوی جدید انتخاب کنید:",
            reply_markup=_partner_rows(B) if partner_id else _main_rows(B, uid),
        )
    B.cancel = stable_cancel

    old_router = B.router
    async def stable_router(update, context):
        uid = update.effective_user.id
        text = (getattr(update.message, "text", "") or "").strip()
        st = B.S.setdefault(uid, {})

        if text == RESTART:
            # Start again is intentionally available from menus and never asks
            # the user to type /start.
            B.S[uid] = {}
            if hasattr(B, "start"):
                return await B.start(update, context)

        # Validate subscriber/mobile input only after the prompt has been sent.
        # Do not run this validation when the callback itself is the prompt.
        if st.get("mode") in {"gov_phone", "subscriber_phone", "mobile"}:
            phone = norm_phone(text)
            if not phone:
                return await update.message.reply_text(
                    "❌ شماره موبایل مشترک صحیح نیست.\n\nشماره را به شکل 09xxxxxxxxx وارد کنید.",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st["gov_phone"] = phone
            # Preserve the legacy flow by moving to its next state when known.
            st["mode"] = "gov_dob"
            return await update.message.reply_text(
                "🎂 تاریخ تولد مشترک را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )

        return await old_router(update, context)
    B.router = stable_router

    # ---------- Rubika ----------
    try:
        import rubika_v2 as R
        old_rhandle = R.handle
        def rubika_handle(uid, chat, x, u):
            x = str(x or "").strip()
            st = R.STATE.setdefault(str(uid), {})
            if x == RESTART:
                st.clear()
                st.update({"lang": "fa", "step": "language"})
                return R.send(chat, R.TEXT["fa"]["lang"], [["1", "🇮🇷 فارسی"], ["2", "🇬🇧 English"], ["3", "🇸🇦 العربية"]])
            # Same mobile normalization on Rubika.
            if st.get("step") in {"gov_phone", "subscriber_phone", "mobile"}:
                phone = norm_phone(x)
                if not phone:
                    return R.send(chat, "❌ شماره موبایل مشترک صحیح نیست.\nشماره را به شکل 09xxxxxxxxx وارد کنید.", [["0", R.CANCEL]])
                st["phone"] = phone
            return old_rhandle(uid, chat, x, u)
        R.handle = rubika_handle

        # Shared service state: Rubika checks the same services table that the
        # Telegram admin panel edits, so opening/closing a service is global.
        old_send = R.send
        R._netyar_v2_original_send = old_send
    except Exception:
        log.exception("Rubika v2 layer could not be installed")

    B._production_v2_installed = True
    log.info("production v2 stability layer installed")
