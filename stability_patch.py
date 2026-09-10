"""Final reliability layer for Telegram text flows and admin bot management.

This module is intentionally additive: it wraps the existing router instead of
replacing the service implementation, so existing Telegram/Rubika behaviour is
preserved while common text aliases, FIDA completion, and bot management are
made deterministic.
"""
import logging
import re

log = logging.getLogger("netyar.stability")


def install():
    import bot as B

    if getattr(B, "_netyar_stability_installed", False):
        return

    original_router = B.router
    original_admin_text = B.admin_text

    aliases = {
        # English -> Persian canonical text
        "🪪 FIDA non-in-person": "🪪 فیدای غیر حضوری",
        "🖨 Printing": "🖨 خدمات چاپ",
        "🏛 Government access issue": "🏛 حل مشکل ورود اتباع دولت من",
        "🎫 Follow-up": "🎫 پیگیری",
        "📱 SIM services": "📱 خدمات سیم کارت",
        "📝 Screening test": "📝 آزمون غربالگری",
        "💰 My wallet": "💰 کیف پول من",
        "📞 Contact us": "📞 تماس با ما",
        "📝 Customer complaints": "📝 ثبت شکایت مشتریان",
        "👥 Partner panel": "👥 پنل همکاران",
        "🛠 Admin panel": "🛠 پنل مدیریت بات",
        "➕ Top up": "➕ شارژ حساب",
        "🔎 Track code": "🔎 پیگیری کد",
        "📋 History": "📋 سوابق",
        "💰 Balance": "💰 موجودی",
        "🚪 Exit panel": "🚪 خروج از پنل",
        "❌ Cancel": B.CANCEL,
        # Arabic -> Persian canonical text
        "🪪 خدمة فيدا": "🪪 فیدای غیر حضوری",
        "🖨 خدمات الطباعة": "🖨 خدمات چاپ",
        "🏛 مشكلة خدمات الحكومة": "🏛 حل مشکل ورود اتباع دولت من",
        "🎫 متابعة": "🎫 پیگیری",
        "📱 خدمات الشريحة": "📱 خدمات سیم کارت",
        "📝 اختبار الفحص": "📝 آزمون غربالگری",
        "💰 محفظتي": "💰 کیف پول من",
        "📞 اتصل بنا": "📞 تماس با ما",
        "📝 شكاوى العملاء": "📝 ثبت شکایت مشتریان",
        "👥 لوحة الشركاء": "👥 پنل همکاران",
        "🛠 لوحة الإدارة": "🛠 پنل مدیریت بات",
        "➕ شحن الحساب": "➕ شارژ حساب",
        "🔎 رمز المتابعة": "🔎 پیگیری کد",
        "📋 السجل": "📋 سوابق",
        "💰 الرصيد": "💰 موجودی",
        "🚪 خروج من اللوحة": "🚪 خروج از پنل",
        "❌ إلغاء": B.CANCEL,
        # Common Persian variants
        "فیدا": "🪪 فیدای غیر حضوری",
        "پیگیری کد رهگیری": "🎫 پیگیری",
        "کد رهگیری": "🎫 پیگیری",
        "پنل همکار": "👥 پنل همکاران",
        "پنل همکاران": "👥 پنل همکاران",
        "خدمات چاپ": "🖨 خدمات چاپ",
        "آزمون غربالگری و پیگیری": "📝 آزمون غربالگری",
    }

    def canon(text):
        text = str(text or "").strip()
        return aliases.get(text, text)

    async def router(update, context):
        msg = getattr(update, "message", None)
        if msg is not None:
            try:
                text = canon(msg.text)
                uid = update.effective_user.id
                st = B.S.setdefault(uid, {})

                # ----- Admin: add/manage messenger bot -----
                if B.admin(uid):
                    if text == "🤖 افزودن بات":
                        st["mode"] = "bot_platform"
                        return await msg.reply_text(
                            "🤖 افزودن بات جدید\n\nپیام‌رسان را انتخاب کنید:",
                            reply_markup=B.kb([["🤖 Telegram", "🤖 Rubika"], ["🤖 Bale", "🤖 Eitaa"], ["⬅️ بازگشت"]]),
                        )
                    if text == "🤖 بات‌های متصل":
                        rows = B.db.bots()
                        if not rows:
                            body = "🤖 هنوز باتی در پنل ثبت نشده است."
                        else:
                            body = "🤖 بات‌های ثبت‌شده:\n\n" + "\n".join(
                                f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}"
                                for r in rows
                            )
                        return await msg.reply_text(body, reply_markup=B.amenu())
                    if text == "🌐 زبان‌ها":
                        return await msg.reply_text(
                            "🌐 مدیریت زبان‌ها\n\nزبان‌های فعال: فارسی، English، العربية\n\nتغییر زبان کاربر از منوی شروع انجام می‌شود و متن گزینه‌ها با همان زبان نمایش داده می‌شود.",
                            reply_markup=B.amenu(),
                        )
                    if text == "🩺 سلامت ربات‌ها":
                        return await msg.reply_text(
                            "🩺 سلامت ربات‌ها\n\nTelegram: توسط webhook اصلی بررسی می‌شود.\nRubika: توسط webhook و watchdog بررسی می‌شود.\nBale/Eitaa: فقط در صورت داشتن آداپتر و API سازگار قابل فعال‌سازی واقعی هستند.",
                            reply_markup=B.amenu(),
                        )

                # ----- Bot setup state machine -----
                if B.admin(uid) and st.get("mode") == "bot_platform":
                    platform = {
                        "🤖 Telegram": "telegram",
                        "🤖 Rubika": "rubika",
                        "🤖 Bale": "bale",
                        "🤖 Eitaa": "eitaa",
                    }.get(text)
                    if platform:
                        st["bot_platform"] = platform
                        st["mode"] = "bot_name"
                        return await msg.reply_text("🤖 نام این بات را وارد کنید:", reply_markup=B.kb([["⬅️ بازگشت"], [B.CANCEL]]))
                    if text == "⬅️ بازگشت":
                        st["mode"] = None
                        return await msg.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())

                if B.admin(uid) and st.get("mode") == "bot_name":
                    if text in {"⬅️ بازگشت", B.CANCEL}:
                        st["mode"] = None
                        return await msg.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
                    if len(text) < 2:
                        return await msg.reply_text("❌ نام بات خیلی کوتاه است. دوباره وارد کنید.", reply_markup=B.kb([[B.CANCEL]]))
                    st["bot_name"] = text
                    st["mode"] = "bot_api"
                    return await msg.reply_text("🔑 API / Token بات را ارسال کنید:", reply_markup=B.kb([[B.CANCEL]]))

                if B.admin(uid) and st.get("mode") == "bot_api":
                    if text in {"⬅️ بازگشت", B.CANCEL}:
                        st["mode"] = None
                        return await msg.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
                    if len(text) < 5:
                        return await msg.reply_text("❌ API معتبر به نظر نمی‌رسد. مقدار کامل API/Token را ارسال کنید.", reply_markup=B.kb([[B.CANCEL]]))
                    platform = st.get("bot_platform", "unknown")
                    name = st.get("bot_name", "Bot")
                    B.db.add_bot(platform, name, text)
                    # Mark only platforms with a running adapter as active. For Bale/Eitaa
                    # we retain the credential as configured without falsely claiming that
                    # a receiver is running.
                    if platform in {"telegram", "rubika"}:
                        B.db.conn.execute("UPDATE bot_integrations SET active=1,status='active',updated_at=? WHERE platform=?", (B.now(), platform))
                        B.db.conn.commit()
                        status = "فعال"
                    else:
                        status = "ثبت‌شده؛ نیازمند آداپتر پیام‌رسان"
                    st["mode"] = None
                    return await msg.reply_text(f"✅ بات ثبت شد.\n🤖 {name}\n📡 {platform}\n📌 وضعیت: {status}", reply_markup=B.amenu())

                # ----- Complete the previously dangling FIDA flow -----
                if st.get("mode") == "fida_phone":
                    phone = B.normalize_phone(text)
                    if not phone:
                        return await msg.reply_text("❌ شماره موبایل معتبر نیست. شماره را به شکل 09xxxxxxxxx وارد کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
                    st["phone"] = phone
                    amount = int(B.db.setting("price_fida", "0") or 0)
                    owner = st.get("partner_id") or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
                    rid, code = B.db.create_request(owner, "fida", "telegram", amount)
                    B.db.answer(rid, "document", file_id=st.get("doc", ""))
                    B.db.answer(rid, "phone", answer=phone)
                    B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid' WHERE id=?", (rid,))
                    B.db.conn.commit()
                    st["mode"] = None
                    try:
                        await B.notify_admins(context.application, f"🆕 درخواست فیدای غیر حضوری\n🎫 {code}\n📱 {phone}", rid)
                    except Exception:
                        log.exception("FIDA admin notification failed")
                    return await msg.reply_text(f"✅ درخواست فیدای غیر حضوری ثبت شد.\n🎫 کد پیگیری: {code}", reply_markup=B.partner_kb(st.get("lang", "fa")) if st.get("partner_id") else B.main(uid))

                # Keep the canonical text only for this dispatch. Do not mutate the
                # PTB Message object (it is immutable-ish in newer PTB versions).
                if text != getattr(msg, "text", ""):
                    class _MsgProxy:
                        def __init__(self, base, value): self._base, self.text = base, value
                        def __getattr__(self, name): return getattr(self._base, name)
                    class _UpdProxy:
                        def __init__(self, base, message): self._base, self.message = base, message
                        def __getattr__(self, name): return getattr(self._base, name)
                    msg = _MsgProxy(msg, text)
                    update = _UpdProxy(update, msg)
                return await original_router(update, context)
            except Exception:
                log.exception("stability router failed")
        return await original_router(update, context)

    B.router = router
    B._netyar_stability_installed = True
    log.info("NetYar stability patch installed")
