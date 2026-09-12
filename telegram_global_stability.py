"""Stable Telegram UI layer.

Normal navigation is rendered with inline buttons. Labels are clean text
without artificial color-prefix emojis. Cancel returns to the current logical
menu instead of unexpectedly switching to another menu.
"""


def _clean(label):
    s = str(label or "").strip()
    for prefix in ("🟦 ", "🟩 ", "🟨 ", "🔵 "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s


def _rows(rows):
    return [[_clean(x) for x in row] for row in rows]


def _lang(B, uid):
    return B.S.get(uid, {}).get("lang", "fa")


def _main(B, uid):
    lang = _lang(B, uid)
    if lang == "en":
        rows = [["FIDA service", "Printing"],
                ["Government access", "Card renewal tracking"],
                ["SIM services", "Screening"],
                ["Tracking", "My wallet"],
                ["Contact us", "Customer complaint"]]
        if B.admin(uid): rows.append(["Admin panel"])
        rows += [["Partner panel"]]
        return B.kb(_rows(rows))
    if lang == "ar":
        rows = [["خدمة فيدا", "خدمات الطباعة"],
                ["خدمات الحكومة", "متابعة تجديد البطاقة"],
                ["خدمات الشريحة", "الفحص"],
                ["المتابعة", "محفظتي"],
                ["اتصل بنا", "شكوى العميل"]]
        if B.admin(uid): rows.append(["لوحة الإدارة"])
        rows += [["لوحة الشركاء"]]
        return B.kb(_rows(rows))
    rows = [["فیدای غیر حضوری", "خدمات چاپ"],
            ["حل مشکل ورود اتباع دولت من", "کد رهگیری تمدید کارت‌ها"],
            ["خدمات سیم کارت", "آزمون غربالگری"],
            ["پیگیری", "کیف پول من"],
            ["تماس با ما", "ثبت شکایت مشتریان"]]
    if B.admin(uid): rows.append(["پنل مدیریت بات"])
    rows += [["پنل همکاران"]]
    return B.kb(_rows(rows))


def _partner(B, lang="fa"):
    if lang == "en":
        rows = [["Top up account", "Government access issue"],
                ["Track code", "History"], ["Balance"],
                ["Ticket to management"], ["Exit panel"]]
    elif lang == "ar":
        rows = [["شحن الحساب", "حل مشكلة خدمات الحكومة"],
                ["رمز المتابعة", "السجل"], ["الرصيد"],
                ["إرسال تذكرة إلى الإدارة"], ["خروج من اللوحة"]]
    else:
        rows = [["شارژ حساب", "حل مشکل سامانه دولت من"],
                ["پیگیری کد", "سوابق"], ["موجودی"],
                ["تیکت به مدیریت"], ["خروج از پنل"]]
    return B.kb(_rows(rows))


def _partner_menu_text(B, uid):
    return _partner(B, _lang(B, uid))


def _is_admin_mode(mode):
    return str(mode or "").startswith("admin") or mode in {"ticket_admin_reply", "admin_ticket_reply"}


def _is_partner_mode(mode):
    return str(mode or "").startswith("partner") or mode in {"ticket_partner", "partner_ticket_chat"}


def install(B):
    if getattr(B, "_telegram_global_stability_installed", False):
        return
    if not hasattr(B, "_original_main_for_global_stability"):
        B._original_main_for_global_stability = B.main

    B.main = lambda uid: _main(B, uid)
    B.partner_kb = lambda lang="fa": _partner(B, lang)

    original_cancel = B.cancel
    async def cancel(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        status = st.get("status", "foreign")
        lang = st.get("lang", "fa")
        mode = st.get("mode")

        # Ticket/data-entry cancellation returns to the menu belonging to the
        # current context; it never jumps to an unrelated menu.
        if mode in {"partner_exit_choice", "p_phone", "p_pass"}:
            return await original_cancel(update, context)
        if _is_admin_mode(mode):
            st["mode"] = "admin"
            await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=B.amenu())
            return
        if _is_partner_mode(mode) or st.get("partner") or st.get("partner_id"):
            st["mode"] = "partner"
            await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=_partner_menu_text(B, uid))
            return

        st["mode"] = None
        # Keep Iranian users in the Iranian menu; foreign users stay in the
        # foreign main menu. The citizenship state is never silently changed.
        if status == "iranian":
            if lang == "en":
                kb = B.kb([["Tracking"], ["Partner panel"]])
            elif lang == "ar":
                kb = B.kb([["المتابعة"], ["لوحة الشركاء"]])
            else:
                kb = B.kb([["پیگیری"], ["پنل همکاران"]])
        else:
            kb = _main(B, uid)
        msg = "❌ Cancelled." if lang == "en" else "❌ تم الإلغاء." if lang == "ar" else "❌ عملیات لغو شد."
        await update.message.reply_text(msg, reply_markup=kb)

    B.cancel = cancel
    B._telegram_global_stability_installed = True
