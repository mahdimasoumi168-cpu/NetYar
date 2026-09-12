"""Iranian subscriber UX, complaints, contact and editable labels."""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger("netyar.telegram.iranian")
CONTACT_USERNAME = "Good_ok_2000"

OPTION_DEFAULTS = {
    "ir_gov": "🏛 حل مشکل ورود اتباع دولت من",
    "ir_track": "🎫 پیگیری",
    "ir_wallet": "💰 کیف پول من",
    "contact": "📞 تماس با ما",
    "complaint": "📝 ثبت شکایت",
    "partner": "🔵 👥 پنل همکاران",
}

TEXT_DEFAULTS = {
    "iranian": "🇮🇷 منوی مشترکین ایرانی\n\nخدمات عادی برای مشترکین ایرانی غیرفعال است. گزینه فعال موردنظر را انتخاب کنید:",
    "complaint_prompt": "📝 ثبت شکایت\n\nمتن شکایت یا انتقاد خود را ارسال کنید.",
    "complaint_ok": "✅ شکایت شما برای مدیریت ارسال شد.",
}


def _get(B, key, default):
    try:
        return B.db.setting("ui_text_" + key, default) or default
    except Exception:
        return default


def _menu(B):
    g = _get(B, "ir_gov", OPTION_DEFAULTS["ir_gov"])
    tr = _get(B, "ir_track", OPTION_DEFAULTS["ir_track"])
    wa = _get(B, "ir_wallet", OPTION_DEFAULTS["ir_wallet"])
    co = _get(B, "contact", OPTION_DEFAULTS["contact"])
    cp = _get(B, "complaint", OPTION_DEFAULTS["complaint"])
    pa = _get(B, "partner", OPTION_DEFAULTS["partner"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(g, callback_data="ir:gov")],
        [InlineKeyboardButton(tr, callback_data="ir:track"), InlineKeyboardButton(wa, callback_data="ir:wallet")],
        [InlineKeyboardButton(co, url=f"https://t.me/{CONTACT_USERNAME}"), InlineKeyboardButton(cp, callback_data="ir:complaint")],
        [InlineKeyboardButton(pa, callback_data="ir:partner")],
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="ir:restart")],
    ])


def install(app, B):
    if getattr(B, "_iranian_complaints_installed", False):
        return

    old_status = B.statuscb

    async def status(update, context):
        q = update.callback_query
        if q.data != "st:iranian":
            return await old_status(update, context)
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        st.update({"status": "iranian"})
        st.pop("mode", None)
        return await q.message.reply_text(
            _get(B, "iranian", TEXT_DEFAULTS["iranian"]),
            reply_markup=_menu(B),
        )

    async def cb(update, context):
        q = update.callback_query
        a = q.data or ""
        if not a.startswith("ir:"):
            return
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        act = a.split(":", 1)[1]

        if act == "gov":
            st["mode"] = "gov_doc_type"
            return await q.message.reply_text(
                "🪪 نوع مدرک مشترک را انتخاب کنید:",
                reply_markup=B.kb([["🪪 کارت آمایش", "🛂 گذرنامه"], ["📗 دفترچه اقامت"], [B.CANCEL]]),
            )
        if act == "track":
            st["mode"] = "track"
            return await q.message.reply_text(
                "🎫 کد پیگیری را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        if act == "wallet":
            try:
                return await B.customer_wallet(update, context)
            except Exception:
                return await q.message.reply_text("💰 کیف پول من\n\nموجودی کیف پول شما در دسترس است.", reply_markup=_menu(B))
        if act == "partner":
            st["mode"] = "p_phone"
            return await q.message.reply_text(
                "📱 شماره همراه همکار را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        if act == "complaint":
            st["mode"] = "iranian_complaint"
            return await q.message.reply_text(_get(B, "complaint_prompt", TEXT_DEFAULTS["complaint_prompt"]))
        if act == "restart":
            st.clear()
            st["lang"] = "fa"
            return await B.start(update, context)

    async def complaint_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "iranian_complaint":
            return
        t = (update.message.text or "").strip()
        u = update.effective_user
        if not t:
            return await update.message.reply_text("❌ متن شکایت خالی است.")
        username = f"@{u.username}" if u.username else "ندارد"
        msg = (
            "📝 شکایت/انتقاد جدید\n\n"
            f"👤 نام: {u.full_name or '-'}\n"
            f"🔹 آیدی عددی: {u.id}\n"
            f"🔹 یوزرنیم: {username}\n\n"
            f"💬 متن شکایت:\n{t}"
        )
        try:
            await B.notify_admins(context.application, msg)
        except Exception:
            log.exception("complaint notification failed")
        st["mode"] = None
        return await update.message.reply_text(
            _get(B, "complaint_ok", TEXT_DEFAULTS["complaint_ok"]),
            reply_markup=_menu(B),
        )

    app.add_handler(CallbackQueryHandler(status, pattern=r"^st:iranian$"), group=-10)
    app.add_handler(CallbackQueryHandler(cb, pattern=r"^ir:"), group=-9)
    # Only consume text when the user is actually submitting a complaint.
    # Never call the generic text router here; doing so can duplicate/steal other flows.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_text), group=-10)
    B._iranian_complaints_installed = True
