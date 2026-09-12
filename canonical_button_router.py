"""Canonical final Telegram button routing.

One deterministic callback router for the final UI. Legacy callbacks are
translated to their visible labels and then dispatched to the existing
business handlers. Navigation controls are intentionally limited to contexts
where they make sense.
"""
import logging
log = logging.getLogger("netyar.canonical_buttons")


def install():
    import bot as B
    import telegram_runtime as TG
    from telegram import CallbackQueryHandler
    from final_platform_fix import _actions, _remember
    from final_ui_flow_patch import _UI

    if getattr(B, "_canonical_button_router", False):
        return

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
        return await q.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))
    B.statuscb = statuscb

    aliases = {
        "🔵 👥 پنل همکاران":"👥 پنل همکاران", "🔵 👥 Partner panel":"👥 پنل همکاران",
        "🔵 👥 لوحة الشركاء":"👥 پنل همکاران", "👥 Partner panel":"👥 پنل همکاران",
        "👥 لوحة الشركاء":"👥 پنل همکاران", "پنل همکاران":"👥 پنل همکاران",
        "🔵 🛠 پنل مدیریت بات":"🛠 پنل مدیریت بات", "🛠 پنل مدیریت":"🛠 پنل مدیریت بات",
        "🛠 Admin panel":"🛠 پنل مدیریت بات", "🛠 لوحة الإدارة":"🛠 پنل مدیریت بات",
        "🎫 Tracking":"🎫 پیگیری", "🎫 متابعة":"🎫 پیگیری",
        "🪪 FIDA non-in-person":"🪪 فیدای غیر حضوری", "🖨 Printing":"🖨 خدمات چاپ",
        "🏛 Government access issue":"🪪 حل مشکل ورود اتباع دولت من",
        "🎫 Tracking code":"🎫 کد رهگیری تمدید کارت‌ها", "📱 SIM services":"📱 خدمات سیم کارت",
        "📝 Screening test":"📝 آزمون غربالگری", "❌ Cancel":"❌ انصراف", "❌ إلغاء":"❌ انصراف",
        "❌ لغو":"❌ انصراف", "لغو":"❌ انصراف", "انصراف":"❌ انصراف",
    }
    def norm(label):
        return aliases.get(str(label or "").strip(), str(label or "").strip())

    def label_for_callback(data):
        data = str(data or "")
        if data.startswith("ik:"):
            return norm(_actions.get(data, ""))
        if data.startswith("ui:"):
            return norm(_UI.get(data, (None, ""))[1])
        return ""

    async def dispatch(update, context):
        q = update.callback_query
        label = label_for_callback(q.data)
        if not label:
            await q.answer("این گزینه منقضی شده؛ لطفاً /start را بزنید.")
            return
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        try:
            if label == "👥 پنل همکاران":
                return await B.partner(update, context)
            if label == "🛠 پنل مدیریت بات":
                if not B.admin(uid):
                    return await q.message.reply_text("❌ دسترسی مدیریت ندارید.", reply_markup=B.main(uid))
                return await q.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            if label == "🚪 خروج از پنل":
                return await B.partner_exit(update, context)
            if label == "❌ انصراف":
                return await B.cancel(update, context)
            if label == "🎫 پیگیری" and st.get("status") == "iranian":
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                q.message.text = label
                return await B.service_text(fake, context)
            if label == "🎫 پیگیری":
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                q.message.text = label
                return await B.ptext(fake, context)
            if label == "➕ شارژ حساب":
                st["mode"] = "topup_amount"
                return await q.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            if label == "🔎 پیگیری کد": return await B.ptrack(update, context)
            if label == "📋 سوابق": return await B.phistory(update, context)
            if label == "💰 موجودی":
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                q.message.text = label
                return await B.router(fake, context)
            if label in {"🪪 فیدای غیر حضوری", "🪪 فیدا"}: return await B.fida(update, context)
            if label == "🖨 خدمات چاپ": return await B.prt(update, context)
            if label in {"🪪 حل مشکل ورود اتباع دولت من", "🏛 حل مشکل سامانه دولت من"}: return await B.gov(update, context)

            # All other buttons go through the authoritative existing handlers.
            fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
            q.message.text = label
            if B.admin(uid):
                result = await B.admin_text(fake, context)
                if result is not None: return result
            result = await B.router(fake, context)
            if result is not None: return result
            return await q.message.reply_text("❌ این گزینه در حال حاضر در دسترس نیست.", reply_markup=B.main(uid))
        except Exception:
            log.exception("canonical button failed: %r", label)
            try: await q.message.reply_text("❌ اجرای گزینه با خطا مواجه شد.", reply_markup=B.main(uid))
            except Exception: pass

    # Highest priority: catches both current ui:* and the older ik:* callbacks.
    old_build = TG.build
    def build():
        app = old_build()
        app.add_handler(CallbackQueryHandler(dispatch, pattern=r"^(ui|ik):"), group=-100)
        return app
    TG.build = build
    B._canonical_button_router = True
    log.info("Canonical final Telegram button router installed")
