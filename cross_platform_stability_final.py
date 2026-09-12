"""Final cross-platform stability layer for Telegram and Rubika."""
from __future__ import annotations
import logging
log = logging.getLogger("netyar.cross_platform_stability_final")


def _telegram():
    import bot as B
    from telegram import ReplyKeyboardMarkup

    # This function is called both before and after legacy modules. The menu
    # must therefore be reapplied every time, while handlers are wrapped once.
    def modern_amenu(*_args, **_kwargs):
        return B.kb([
            ["👥 کاربران", "🤝 همکاران"],
            ["📋 درخواست‌ها", "🎫 تیکت‌ها"],
            ["🟢/🔴 خدمات ایرانی", "🟢/🔴 خدمات اتباع"],
            ["💰 قیمت خدمات", "📝 تغییر متن‌ها"],
            ["📎 مدارک و فایل‌ها", "👤 مدیران"],
            ["🤖 پیام‌رسان‌ها", "📊 گزارش‌ها"],
            ["⚙️ تنظیمات پایه", "📞 پشتیبانی"],
            ["💬 ارتباط با همکار"],
            ["⬅️ منوی اصلی"],
        ])
    B.amenu = modern_amenu

    if getattr(B, "_cross_platform_stability_final_telegram_initialized", False):
        return

    old_exit = getattr(B, "partner_exit_choice", None)
    if old_exit:
        async def stable_exit(update, context):
            uid = update.effective_user.id
            st = B.S.setdefault(uid, {})
            text = (getattr(update.message, "text", "") or "").strip()
            if st.get("mode") != "partner_exit_choice":
                return await old_exit(update, context)
            if text in {"🔒 خروج دائمی", "🔒 Permanent exit", "🔒 خروج دائم"}:
                status, lang = st.get("status", "foreign"), st.get("lang", "fa")
                B.S[uid] = {"status": status, "lang": lang}
                if status == "iranian":
                    kb = B.kb([["🎫 پیگیری", "👥 پنل همکاران"], [B.CANCEL]])
                    msg = {"fa":"🔒 خروج دائمی انجام شد.\n🇮🇷 به منوی ایرانی برگشتید.","en":"🔒 Permanent exit completed.\n🇮🇷 Back to the Iranian menu.","ar":"🔒 تم تسجيل الخروج الدائم.\n🇮🇷 عدت إلى قائمة الإيرانيين."}.get(lang)
                else:
                    kb = B.main(uid)
                    msg = {"fa":"🔒 خروج دائمی انجام شد.\n🪪 به منوی اتباع برگشتید.","en":"🔒 Permanent exit completed.\n🪪 Back to the foreign-resident menu.","ar":"🔒 تم تسجيل الخروج الدائم.\n🪪 عدت إلى قائمة المقيمين الأجانب."}.get(lang)
                return await update.message.reply_text(msg, reply_markup=kb)
            if text in {B.CANCEL, "❌ Cancel", "❌ إلغاء", "لغو"}:
                st["mode"] = None
                kb = B.kb([["🎫 پیگیری", "👥 پنل همکاران"], [B.CANCEL]]) if st.get("status") == "iranian" else B.main(uid)
                return await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=kb)
            return await old_exit(update, context)
        B.partner_exit_choice = stable_exit

    old_partner_kb = getattr(B, "partner_kb", None)
    if old_partner_kb:
        def stable_partner_kb(lang="fa"):
            markup = old_partner_kb(lang)
            try:
                rows = [list(r) for r in markup.keyboard]
                if not any(B.CANCEL in [str(x) for x in r] for r in rows):
                    rows.append([B.CANCEL])
                return ReplyKeyboardMarkup(rows, resize_keyboard=True)
            except Exception:
                return markup
        B.partner_kb = stable_partner_kb

    B._cross_platform_stability_final_telegram_initialized = True


def _rubika():
    import rubika_v2 as R
    if getattr(R, "_cross_platform_stability_final_rubika", False):
        return
    old_handle = R.handle
    old_main_rows, old_iran_rows = R.main_rows, R.iran_rows

    def main_rows(uid):
        lang = R.lang(uid)
        if lang == "en":
            return [[("1","🪪 FIDA service"),("2","🖨 Printing")],[("3","🏛 Government access"),("4","🎫 Tracking")],[("5","📱 SIM services"),("6","📝 Screening")],[("7","💰 My wallet"),("8","👥 Partner panel")],[("9","📞 Contact us"),("10","🔄 Start again")]]
        if lang == "ar":
            return [[("1","🪪 خدمة فيدا"),("2","🖨 الطباعة")],[("3","🏛 خدمات الحكومة"),("4","🎫 المتابعة")],[("5","📱 خدمات الشريحة"),("6","📝 الفحص")],[("7","💰 محفظتي"),("8","👥 لوحة الشركاء")],[("9","📞 اتصل بنا"),("10","🔄 بدء من جديد")]]
        return old_main_rows(uid)

    def iran_rows(uid):
        lang = R.lang(uid)
        if lang == "en": return [[("1","🎫 Tracking"),("2","👥 Partner panel")],[("10","🔄 Start again")]]
        if lang == "ar": return [[("1","🎫 المتابعة"),("2","👥 لوحة الشركاء")],[("10","🔄 بدء من جديد")]]
        return old_iran_rows(uid)

    def partner_rows():
        return [[("1","➕ شارژ حساب"),("2","🔎 پیگیری کد")],[("3","📋 سوابق"),("4","💰 موجودی")],[("5","🏛 حل مشکل سامانه دولت من")],[("6","✉️ تیکت به مدیریت")],[("10","🔄 شروع مجدد"),("0","❌ انصراف")]]

    def admin_rows():
        return [[("1","👥 مدیریت همکاران"),("2","💰 مدیریت شارژها")],[("3","📋 مدیریت درخواست‌ها"),("4","💳 مدیریت پرداخت‌ها")],[("5","🛠 مدیریت خدمات"),("6","📝 مدیریت متن‌ها")],[("7","💵 مدیریت قیمت‌ها"),("8","🤖 مدیریت بات‌ها")],[("9","📊 گزارش‌ها"),("10","👤 مدیریت مدیران")],[("11","🎫 مدیریت تیکت‌ها"),("12","⚙️ تنظیمات")],[("99","🔄 شروع مجدد"),("0","❌ انصراف")]]

    R.main_rows, R.iran_rows, R.partner_rows, R.admin_rows = main_rows, iran_rows, partner_rows, admin_rows

    def is_ticket(step):
        return step in {"partner_ticket", "partner_ticket_chat", "admin_ticket_chat", "admin_ticket_reply", "ticket_admin_reply"}

    def handle(uid, chat, x, update):
        uid, x = str(uid), str(x or "").strip()
        st = R.STATE.setdefault(uid, {})
        step = st.get("step")
        if is_ticket(step):
            if x in {"0", "❌ انصراف", "99", "🔄 شروع مجدد", "cancel", "Cancel", "إلغاء"}:
                st["step"] = "admin" if R.is_admin(uid) else "partner"
                R.send(chat, "✅ گفت‌وگو بسته شد.", R.admin_rows() if R.is_admin(uid) else R.partner_rows())
                return
            if step in {"partner_ticket_chat", "admin_ticket_chat"}:
                target = str(st.get("ticket_admin_chat") or st.get("ticket_partner_chat") or "").strip()
                if not target:
                    phone = str(st.get("ticket_partner_phone") or st.get("partner") or "").strip()
                    target = str(R.db.setting(f"ticket_admin_{phone}", "") or next(iter(R.ADMIN_IDS), "")).strip()
                if not target:
                    R.send(chat, "❌ طرف مقابل برای تیکت پیدا نشد.", [[("0","❌ انصراف")]])
                    return
                if x:
                    prefix = "👔 پیام مدیریت" if R.is_admin(uid) else "📨 پیام همکار"
                    try:
                        R.send(target, f"{prefix}\n\n{x}")
                        R.send(chat, "✅ پیام ارسال شد.", [[("0","❌ انصراف")]])
                    except Exception:
                        log.exception("stable Rubika ticket send failed")
                        R.send(chat, "❌ ارسال پیام انجام نشد.", [[("0","❌ انصراف")]])
                else:
                    R.send(chat, "✉️ پیام را ارسال کنید.\n❌ برای لغو، انصراف را بزنید.", [[("0","❌ انصراف")]])
                return
        return old_handle(uid, chat, x, update)

    R.handle = handle
    R._cross_platform_stability_final_rubika = True


def install():
    try: _telegram()
    except Exception: log.exception("cross-platform Telegram stability install failed")
    try: _rubika()
    except Exception: log.exception("cross-platform Rubika stability install failed")
