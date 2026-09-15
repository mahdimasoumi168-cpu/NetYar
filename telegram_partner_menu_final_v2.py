"""Final Telegram partner-menu consistency layer."""
import logging
log = logging.getLogger("netyar.telegram.partner_menu_final_v2")
PARTNER = "👥 پنل همکاران"
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"

def _menu(B, uid):
    st = B.S.get(uid, {}) or {}
    if st.get("status") == "iranian":
        rows = [["🎫 پیگیری", PARTNER], ["📞 تماس با ما", "🔄 شروع مجدد"]]
    else:
        rows = [
            ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
            ["🪪 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها"],
            ["📱 خدمات سیم کارت", "📝 آزمون غربالگری"],
            ["🎫 پیگیری", "💰 کیف پول من"],
            ["📞 تماس با ما", "📝 ثبت شکایت مشتریان"],
            [PARTNER, "🔄 شروع مجدد"],
        ]
    if B.admin(uid): rows.append(["🛠 پنل مدیریت بات"])
    return B.kb(rows)

def _partner_keyboard(B, uid):
    import telegram_ui_policy_v2 as UI
    return UI.inline([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        [IRANCELL, "🪪 فیدای غیر حضوری"],
        ["🔎 پیگیری کد", "📋 سوابق"],
        ["💰 موجودی", "🎫 تیکت به مدیریت"],
        ["🚪 خروج از پنل"],
        ["❌ انصراف"],
    ], B, uid)

def install(app, B):
    if getattr(B, "_partner_menu_final_v2", False): return
    B.main = lambda uid: _menu(B, uid)
    try:
        import telegram_ui_policy_v2 as UI
        def partner_kb(lang="fa"):
            try: uid = int(UI._uid() or 0)
            except Exception: uid = 0
            return _partner_keyboard(B, uid)
        B.partner_kb = partner_kb
        old_dispatch = UI._dispatch
        async def dispatch(update, context, bot, label):
            label = str(label or "").strip()
            label = {"👥 Partner panel": PARTNER, "👥 لوحة الشركاء": PARTNER, "پنل همکاران": PARTNER}.get(label, label)
            if label == PARTNER:
                q = getattr(update, "callback_query", None)
                uid = q.from_user.id if q else update.effective_user.id
                st = B.S.setdefault(uid, {})
                target = q.message if q else update.effective_message
                if not st.get("partner_id") or not st.get("partner_active", True):
                    st["mode"] = "p_phone"; st["step"] = "partner_phone"
                    return await target.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
                return await target.reply_text("👥 پنل همکاران", reply_markup=_partner_keyboard(B, uid))
            return await old_dispatch(update, context, bot, label)
        UI._dispatch = dispatch
    except Exception:
        log.exception("final partner menu dispatch installation failed")
    B._partner_menu_final_v2 = True
