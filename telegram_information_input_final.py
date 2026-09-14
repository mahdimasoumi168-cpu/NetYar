"""Deterministic final owner for conversational information entry.

This layer runs before legacy text routers so an active information-gathering
state cannot be swallowed by a menu, night-shift, or fallback handler.
"""
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop


def _digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))


def _normalize_phone(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def install(app, B):
    if getattr(B, "_information_input_final", False):
        return

    async def text(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not msg.text:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        mode = str(st.get("mode") or "")
        t = msg.text.strip()
        d = _digits(t)

        # Partner login is handled before every legacy text router. This makes
        # the password step deterministic instead of allowing an unrelated
        # service/admin handler to consume the password and remain silent.
        if mode == "p_phone" or st.get("step") == "partner_phone":
            phone = _normalize_phone(t)
            if not re.fullmatch(r"09\d{9}", phone):
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                await msg.reply_text("❌ شماره موبایل صحیح نیست.\n\n📱 شماره موبایل اختصاصی همکار را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            partner = None
            try:
                partner = B.db.partner(phone)
                if partner and not int(partner["active"] or 0):
                    partner = None
                if not partner:
                    rows = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
                    for candidate in rows:
                        if _normalize_phone(candidate["phone"]) == phone:
                            partner = candidate
                            break
            except Exception:
                partner = None
            if not partner:
                st["mode"] = "p_phone"; st["step"] = "partner_phone"
                await msg.reply_text("❌ این شماره به همکار فعال اختصاص ندارد.\n\n📱 شماره را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            st["partner_phone"] = phone; st["phone"] = phone
            st["partner_id"] = int(partner["id"]) if partner["id"] is not None else None
            st["pending_partner_id"] = st["partner_id"]
            st["mode"] = "p_pass"; st["step"] = "partner_pass"
            await msg.reply_text("🔐 رمز عبور پنل همکاران را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "p_pass" or st.get("step") == "partner_pass":
            phone = _normalize_phone(st.get("partner_phone") or st.get("phone"))
            partner = None
            try:
                if phone:
                    partner = B.db.partner(phone)
                if partner and not int(partner["active"] or 0):
                    partner = None
                if not partner and phone:
                    rows = B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
                    for candidate in rows:
                        if _normalize_phone(candidate["phone"]) == phone:
                            partner = candidate
                            break
            except Exception:
                partner = None
            ok = False
            if partner:
                try:
                    from core import check_password
                    ok = bool(check_password(t, partner["password_hash"]))
                except Exception:
                    try:
                        ok = bool(B.check_password(t, partner["password_hash"]))
                    except Exception:
                        ok = False
            if not ok:
                st["mode"] = "p_pass"; st["step"] = "partner_pass"
                await msg.reply_text("❌ رمز عبور نادرست است.\n\n🔐 رمز عبور پنل همکاران را دوباره وارد کنید:")
                raise ApplicationHandlerStop
            st["partner"] = phone; st["partner_phone"] = phone; st["phone"] = phone
            st["partner_id"] = int(partner["id"]) if partner["id"] is not None else None
            st["partner_active"] = True; st["partner_logged_out"] = False
            st["mode"] = "partner"; st["step"] = "partner"
            st.pop("pending_partner_id", None)
            try:
                B.db.set_setting(f"partner_chat_{phone}", str(uid))
                if st.get("partner_id"):
                    B.db.set_setting(f"partner_chat_{st['partner_id']}", str(uid))
            except Exception:
                pass
            balance = int(partner["balance"] or 0)
            try:
                markup = B.partner_kb(st.get("lang", "fa"))
            except Exception:
                markup = None
            kwargs = {"reply_markup": markup} if markup is not None else {}
            await msg.reply_text(
                f"✅ ورود با موفقیت انجام شد.\n\n👥 پنل همکاران\n👤 {partner['name'] or '-'}\n📱 {phone}\n💰 اعتبار قابل استفاده: {balance:,} تومان\n\nگزینه موردنظر را انتخاب کنید:",
                **kwargs,
            )
            raise ApplicationHandlerStop

        if mode == "govv2_phone":
            phone = re.sub(r"\D", "", d)
            if phone.startswith("98"):
                phone = "0" + phone[2:]
            if not re.fullmatch(r"09\d{9}", phone):
                await msg.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.")
            else:
                st["gov_phone"] = phone
                st["mode"] = "govv2_dob"
                await msg.reply_text("🎂 تاریخ تولد مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "govv2_dob":
            if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", t):
                await msg.reply_text("❌ تاریخ تولد را به شکل 1356/01/01 وارد کنید.")
            else:
                st["gov_dob"] = t; st["mode"] = "govv2_unique"
                await msg.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "govv2_unique":
            if len(d) < 3:
                await msg.reply_text("❌ شناسه یکتا را صحیح وارد کنید.")
            else:
                st["gov_unique"] = d; st["mode"] = "govv2_special"
                await msg.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "govv2_special":
            if not re.fullmatch(r"1\d{11}", d):
                await msg.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.")
            else:
                st["gov_special"] = d
                typ = st.get("gov_doc_type")
                if typ == "card":
                    st["mode"] = "govv2_family"
                    await msg.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (فقط برای کارت آمایش):")
                else:
                    st["mode"] = "govv2_identity_number"
                    prompt = {"passport": "🛂 شماره گذرنامه مشترک را وارد کنید:", "residence_booklet": "📗 شماره دفترچه اقامت مشترک را وارد کنید:", "temporary_card": "🪪 شماره کارت موقت مشترک را وارد کنید:"}.get(typ, "🪪 شماره مدرک مشترک را وارد کنید:")
                    await msg.reply_text(prompt)
            raise ApplicationHandlerStop

        if mode == "govv2_family":
            if not d.isdigit():
                await msg.reply_text("❌ کد خانوار باید عددی باشد.")
            else:
                st["gov_family_code"] = d; st["mode"] = "govv2_postal"
                await msg.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "govv2_identity_number":
            if len(d) < 3:
                await msg.reply_text("❌ شماره مدرک را صحیح وارد کنید.")
            else:
                st["gov_identity_number"] = d; st["mode"] = "govv2_postal"
                await msg.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:")
            raise ApplicationHandlerStop

        if mode == "govv2_postal":
            if not re.fullmatch(r"\d{10}", d):
                await msg.reply_text("❌ کد پستی باید دقیقاً ۱۰ رقم باشد.")
            else:
                st["gov_postal"] = d
                if st.get("gov_doc_type") == "passport":
                    st["mode"] = "govv2_passport_photo1"
                    await msg.reply_text("📸 ۱/۳ — لطفاً عکس صفحه اول پاسپورت مشترک را ارسال کنید:")
                else:
                    st["mode"] = "govv2_photo"
                    await msg.reply_text("📸 حالا تصویر مدرک مشترک را ارسال کنید:")
            raise ApplicationHandlerStop

        if mode == "topup_amount":
            raw = d.replace(",", "").replace("٬", "").replace(" ", "").replace("تومان", "")
            if not raw.isdigit() or int(raw) <= 0:
                await msg.reply_text("❌ مبلغ نامعتبر است. فقط عدد وارد کنید؛ مثال: 500000")
                raise ApplicationHandlerStop
            st["topup_amount"] = int(raw); st["mode"] = "topup_receipt"
            card = B.db.setting("card_number", "") or ""; owner = B.db.setting("card_owner", "") or ""
            await msg.reply_text(f"🧾 فاکتور شارژ حساب\n\n💰 مبلغ: {int(raw):,} تومان\n💳 شماره کارت: {card or '-'}\n👤 به نام: {owner or '-'}\n\n📸 پس از واریز، تصویر رسید را ارسال کنید.")
            raise ApplicationHandlerStop

        if B.admin(uid) and st.get("admin_plus_mode"):
            try:
                import telegram_admin_plus as A
                await A._text(update, context, B)
            except Exception:
                st["admin_plus_mode"] = None
                await msg.reply_text("❌ اجرای اطلاعات مدیریت با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
            raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-200000)
    B._information_input_final = True
