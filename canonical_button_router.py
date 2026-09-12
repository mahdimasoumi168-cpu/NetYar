"""Canonical final button routing for Telegram.

This is deliberately the last Telegram UI layer: every inline button is routed
by its visible label to the existing business function instead of passing
through the stack of legacy router wrappers. It also gives Iranian users a
separate, deterministic menu and prevents menu/state leakage between Iranian
and foreign-citizen flows.
"""
import logging
log = logging.getLogger("netyar.canonical_buttons")


def install():
    import bot as B
    import telegram_runtime as TG
    from telegram import CallbackQueryHandler, InlineKeyboardMarkup, InlineKeyboardButton
    from final_ui_flow_patch import _UI, _remember

    if getattr(B, "_canonical_button_router", False):
        return

    # Keep the existing foreign menu implementation, but make the Iranian path
    # explicit so it can never inherit the foreign-citizen service buttons.
    old_main = B.main
    def main(uid):
        st = B.S.get(uid, {})
        if st.get("status") == "iranian":
            rows = [["🎫 پیگیری", "👥 پنل همکاران"]]
            if B.admin(uid):
                rows.append(["🛠 پنل مدیریت بات"])
            return B.kb(rows)
        return old_main(uid)
    B.main = main

    old_statuscb = B.statuscb
    async def statuscb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        status = str(q.data).split(":", 1)[1]
        B.S.setdefault(uid, {})["status"] = status
        if status == "iranian":
            return await q.message.reply_text(
                "🇮🇷 بخش خدمات ایرانی\n\nفعلاً خدمات عمومی برای ایرانی فعال نیست.",
                reply_markup=B.main(uid),
            )
        return await q.message.reply_text(
            "منوی خدمات کمک یار مهاجر 👇",
            reply_markup=B.main(uid),
        )
    B.statuscb = statuscb

    # Label aliases from all existing language/legacy variants.
    def norm(label):
        s = str(label or "").strip()
        aliases = {
            "🔵 👥 پنل همکاران":"👥 پنل همکاران",
            "🔵 👥 Partner panel":"👥 پنل همکاران",
            "🔵 👥 لوحة الشركاء":"👥 پنل همکاران",
            "👥 Partner panel":"👥 پنل همکاران",
            "👥 لوحة الشركاء":"👥 پنل همکاران",
            "پنل همکاران":"👥 پنل همکاران",
            "🔵 🛠 پنل مدیریت بات":"🛠 پنل مدیریت بات",
            "🛠 پنل مدیریت":"🛠 پنل مدیریت بات",
            "🛠 Admin panel":"🛠 پنل مدیریت بات",
            "🛠 لوحة الإدارة":"🛠 پنل مدیریت بات",
            "🎫 Tracking":"🎫 پیگیری",
            "🎫 متابعة":"🎫 پیگیری",
            "🪪 FIDA non-in-person":"🪪 فیدای غیر حضوری",
            "🖨 Printing":"🖨 خدمات چاپ",
            "🏛 Government access issue":"🪪 حل مشکل ورود اتباع دولت من",
            "🎫 Tracking code":"🎫 کد رهگیری تمدید کارت‌ها",
            "📱 SIM services":"📱 خدمات سیم کارت",
            "📝 Screening test":"📝 آزمون غربالگری",
            "❌ Cancel":"❌ انصراف",
            "❌ إلغاء":"❌ انصراف",
        }
        return aliases.get(s, s)

    async def dispatch(update, context):
        q = update.callback_query
        label = _UI.get(str(q.data), (None, ""))[1]
        if not label:
            await q.answer("لطفاً از منوی جدید استفاده کنید.")
            return
        await q.answer()
        label = norm(label)
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})

        try:
            if label == "👥 پنل همکاران":
                return await B.partner(update, context)
            if label == "🛠 پنل مدیریت بات":
                if not B.admin(uid):
                    return await q.message.reply_text("❌ دسترسی مدیریت ندارید.", reply_markup=B.main(uid))
                return await q.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            if label == "🎫 پیگیری" and st.get("status") == "iranian":
                return await B.service_text(type("U", (), {"effective_user":q.from_user,"message":q.message})(), context)
            if label == "🎫 پیگیری":
                return await B.ptext(type("U", (), {"effective_user":q.from_user,"message":q.message})(), context)
            if label in {"🪪 فیدای غیر حضوری", "🪪 فیدا"}:
                return await B.fida(update, context)
            if label in {"🖨 خدمات چاپ"}:
                return await B.prt(update, context)
            if label in {"🪪 حل مشکل ورود اتباع دولت من", "🏛 حل مشکل سامانه دولت من"}:
                return await B.gov(update, context)
            if label == "➕ شارژ حساب":
                st["mode"] = "topup_amount"
                return await q.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            if label == "🔎 پیگیری کد":
                return await B.ptrack(update, context)
            if label == "📋 سوابق":
                return await B.phistory(update, context)
            if label == "💰 موجودی":
                return await B.router(type("U", (), {"effective_user":q.from_user,"message":q.message})(), context)
            if label == "🚪 خروج از پنل":
                return await B.partner_exit(update, context)
            if label == "❌ انصراف":
                return await B.cancel(update, context)
            # Admin menu buttons and all service-specific text buttons use the
            # existing admin/service handlers, but through one stable path.
            if B.admin(uid):
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                q.message.text = label
                result = await B.admin_text(fake, context)
                if result is not None:
                    return result
            fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
            q.message.text = label
            result = await B.router(fake, context)
            if result is not None:
                return result
            return await q.message.reply_text("❌ این گزینه در حال حاضر در دسترس نیست.", reply_markup=B.main(uid))
        except Exception:
            log.exception("canonical button failed: %r", label)
            try:
                await q.message.reply_text("❌ اجرای گزینه با خطا مواجه شد. منوی جدید برای شما ارسال شد.", reply_markup=B.main(uid))
            except Exception:
                pass

    # Register after every older ui:* handler so this canonical handler wins.
    old_build = TG.build
    def build():
        app = old_build()
        app.add_handler(CallbackQueryHandler(dispatch, pattern=r"^ui:"), group=-1)
        return app
    TG.build = build
    B._canonical_button_router = True
    log.info("Canonical final Telegram button router installed")
