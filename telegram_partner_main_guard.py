"""Final Telegram partner-session stability guard.

Keeps authenticated partners inside their panel, makes ui2 callbacks survive
runtime/database refreshes by recovering the visible button label, routes the
partner-to-management chat to an admin destination, and exposes the Irancell
partner service without replacing the existing panel options.
"""
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_main_guard")
PARTNER = "👥 پنل همکاران"
MANAGEMENT = "💬 ارتباط با مدیریت"
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
CANCEL = "❌ انصراف"
START_AGAIN = "🔄 شروع مجدد"
PHONE_MODE = "irancell_partner_phone"


def _visible_label(q):
    try:
        markup = getattr(q.message, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row or []:
                if getattr(button, "callback_data", None) == str(q.data or ""):
                    return str(getattr(button, "text", "") or "").strip()
    except Exception:
        log.exception("visible callback label recovery failed")
    return ""


def _first_admin(B):
    for aid in getattr(B, "ADM", ()) or ():
        try:
            return int(aid)
        except Exception:
            continue
    for aid in getattr(B, "ADMINS", ()) or ():
        try:
            return int(aid)
        except Exception:
            continue
    return None


def _partner_markup(B, uid):
    import telegram_ui_policy_v2 as UI
    return UI.inline([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        [IRANCELL, "🪪 فیدای غیر حضوری"],
        ["📱 خدمات سیم کارت", "🔎 پیگیری کد"],
        ["📋 سوابق", "💰 موجودی"],
        ["🎫 تیکت به مدیریت", MANAGEMENT],
        ["🚪 خروج از پنل"],
        [CANCEL],
    ], B, uid)


def install(app, B):
    if getattr(B, "_partner_main_guard_v24", False):
        return

    original_main = getattr(B, "main", None)
    if not callable(original_main):
        log.warning("B.main is not callable; partner guard skipped")
        return

    def guarded_main(uid):
        try:
            st = B.S.setdefault(uid, {})
            active = bool(
                st.get("partner_id")
                and st.get("partner_active", False)
                and not st.get("partner_logged_out", False)
                and st.get("mode") not in {"p_phone", "p_password", "night_phone", "night_password"}
            )
            if active:
                return _partner_markup(B, uid)
        except Exception:
            log.exception("partner main guard failed; using original main")
        return original_main(uid)

    B.main = guarded_main

    try:
        import telegram_ui_policy_v2 as UI
        old_dispatch = UI._dispatch
        if not getattr(UI, "_partner_stability_v24_dispatch", False):
            async def dispatch(update, context, BB, label):
                label = str(label or "").strip()
                q = getattr(update, "callback_query", None)
                uid = int(q.from_user.id) if q else int(update.effective_user.id)
                st = BB.S.setdefault(uid, {})
                if label == MANAGEMENT:
                    pid = st.get("partner_id")
                    if not pid or not st.get("partner_active", False) or st.get("partner_logged_out"):
                        await (q.message if q else update.effective_message).reply_text(
                            "⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=_partner_markup(BB, uid)
                        )
                        raise ApplicationHandlerStop
                    admin_id = _first_admin(BB)
                    if not admin_id:
                        await (q.message if q else update.effective_message).reply_text(
                            "❌ مدیر برای ارتباط با مدیریت تنظیم نشده است.", reply_markup=_partner_markup(BB, uid)
                        )
                        raise ApplicationHandlerStop
                    try:
                        row = BB.db.conn.execute(
                            "SELECT id,name,phone FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)
                        ).fetchone()
                    except Exception:
                        row = None
                    if not row:
                        st.pop("partner_id", None)
                        st["partner_active"] = False
                        st["mode"] = None
                        await (q.message if q else update.effective_message).reply_text(
                            "⛔ حساب همکار فعال نیست. لطفاً دوباره وارد شوید.", reply_markup=BB.main(uid)
                        )
                        raise ApplicationHandlerStop
                    try:
                        BB.db.set_setting(f"partner_chat_{int(pid)}", str(uid))
                        if row["phone"]:
                            BB.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
                        BB.db.set_setting(f"final_chat_admin_{int(pid)}", str(admin_id))
                    except Exception:
                        log.exception("partner management mapping save failed")
                    st.update(
                        mode="final_partner_chat",
                        final_chat_admin=int(admin_id),
                        final_chat_partner_id=int(pid),
                        chat_reply_pending=False,
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=int(admin_id),
                            text=(
                                "💬 ارتباط با مدیریت از طرف همکار فعال شد.\n\n"
                                f"👤 همکار: {row['name'] or '-'}\n"
                                f"📱 شماره همکار: {row['phone'] or '-'}\n"
                                f"🆔 شناسه همکار: {int(pid)}\n\n"
                                "پیام، عکس، فایل، ویس یا ویدیو همکار برای شما ارسال می‌شود."
                            ),
                        )
                    except Exception:
                        log.exception("partner management notification failed")
                    target = q.message if q else update.effective_message
                    await target.reply_text(
                        "💬 ارتباط با مدیریت فعال شد.\n\n"
                        "حالا پیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\n"
                        "پیام‌ها مستقیماً برای مدیریت ارسال می‌شوند.\n\n"
                        "برای پایان ارتباط، «❌ انصراف» را بزنید.",
                        reply_markup=BB.cancel_kb(st.get("lang", "fa")),
                    )
                    raise ApplicationHandlerStop

                if label == IRANCELL:
                    pid = st.get("partner_id")
                    if not pid or not st.get("partner_active", False) or st.get("partner_logged_out"):
                        target = q.message if q else update.effective_message
                        await target.reply_text(
                            "⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=_partner_markup(BB, uid)
                        )
                        raise ApplicationHandlerStop
                    try:
                        import telegram_irancell_partner_service as IRSIM
                        IRSIM._ensure_service(BB)
                    except Exception:
                        log.exception("Irancell service ensure failed")
                    st["mode"] = PHONE_MODE
                    st.pop("irancell", None)
                    target = q.message if q else update.effective_message
                    await target.reply_text(
                        "📱 حل مشکل سیم کارت ایرانسل\n\n"
                        "📱 شماره موبایل ایرانسل که به نام مشترک ثبت شده است را وارد کنید:\n\n"
                        "💰 هزینه خدمت: ۳۰۰٬۰۰۰ تومان\n"
                        "💳 مبلغ فقط از شارژ پنل همکار کسر می‌شود.\n\n"
                        "بعد از ثبت، درخواست همراه با مدرک و جزئیات برای مدیریت ارسال می‌شود.",
                        reply_markup=BB.cancel_kb(st.get("lang", "fa")),
                    )
                    raise ApplicationHandlerStop
                return await old_dispatch(update, context, BB, label)
            UI._dispatch = dispatch
            UI._partner_stability_v24_dispatch = True
    except Exception:
        log.exception("partner stable dispatch installation failed")

    async def stable_ui2(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("ui2:"):
            return
        # Never preempt the dedicated off-hours guard.
        try:
            from telegram_offhours_partner_gate_v2 import _is_open
            if not _is_open(B):
                return
        except Exception:
            pass
        token = str(q.data)[4:]
        label = ""
        try:
            row = B.db.conn.execute(
                "SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)
            ).fetchone()
            if row:
                if row["user_id"] and str(row["user_id"]) != str(q.from_user.id):
                    await q.answer("این گزینه برای کاربر دیگری است.", show_alert=True)
                    raise ApplicationHandlerStop
                label = str(row["label"] or "").strip()
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("ui2 callback lookup failed")
        if not label:
            label = _visible_label(q)
        if not label:
            await q.answer("این دکمه قابل بازیابی نیست؛ لطفاً از منوی فعلی استفاده کنید.", show_alert=True)
            if B.S.get(q.from_user.id, {}).get("partner_id") and B.S.get(q.from_user.id, {}).get("partner_active"):
                await q.message.reply_text("⛔ این دکمه دیگر معتبر نیست. پنل همکاران شما باز ماند.", reply_markup=_partner_markup(B, q.from_user.id))
            else:
                await q.message.reply_text("🔄 منو به‌روزرسانی شد. لطفاً یکی از گزینه‌های فعلی را انتخاب کنید.", reply_markup=B.main(q.from_user.id))
            raise ApplicationHandlerStop
        try:
            await q.answer()
            await UI._dispatch(update, context, B, label)
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("stable ui2 recovered callback failed label=%r", label)
            st = B.S.setdefault(q.from_user.id, {})
            if st.get("partner_id") and st.get("partner_active") and not st.get("partner_logged_out"):
                await q.message.reply_text(
                    "❌ اجرای این گزینه با خطای موقت روبه‌رو شد؛ پنل همکاران شما حفظ شد. لطفاً دوباره تلاش کنید.",
                    reply_markup=_partner_markup(B, q.from_user.id),
                )
            else:
                await q.message.reply_text("❌ اجرای گزینه با خطای موقت روبه‌رو شد. لطفاً دوباره تلاش کنید.", reply_markup=B.main(q.from_user.id))
            raise ApplicationHandlerStop

    try:
        if not getattr(B, "_partner_stability_v24_ui2_handler", False):
            app.add_handler(CallbackQueryHandler(stable_ui2, pattern=r"^ui2:"), group=-70000)
            B._partner_stability_v24_ui2_handler = True
    except Exception:
        log.exception("stable ui2 handler installation failed")

    try:
        import telegram_irancell_partner_service as IRSIM
        IRSIM._ensure_service(B)
    except Exception:
        log.exception("Irancell partner service registration failed")

    B._partner_main_guard_v24 = True
    log.info("Final partner-session stability v24 installed")
