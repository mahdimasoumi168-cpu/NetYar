"""Deterministic Telegram entry routing for partner/admin panels.

The final runtime installs a single fail-safe owner for ui2 callbacks.
Legacy dispatch wrappers remain available for compatibility, but normal user
buttons are handled by telegram_stable_callback before the older ui2 handler.
"""
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.entry_router_guard")
PARTNER = "👥 پنل همکاران"
ADMIN_PANEL = "🛠 پنل مدیریت بات"
CANCEL = "❌ انصراف"
FIDA = "🪪 فیدای غیر حضوری"
SIM = "📱 خدمات سیم کارت"


def _is_admin(B, uid):
    try:
        return bool(B.admin(uid))
    except Exception:
        log.exception("admin authorization check failed")
        return False


def _partner_markup(B, UI, uid):
    # Canonical partner menu. Service buttons are intentionally partner-facing:
    # the service flows use the partner's charged bot credit, not customer card-to-card.
    rows = [
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        [FIDA, SIM],
        ["🔎 پیگیری کد", "📋 سوابق"],
        ["💰 موجودی", "🎫 تیکت به مدیریت"],
    ]
    if _is_admin(B, uid):
        rows.append([ADMIN_PANEL])
    rows.extend([["🚪 خروج از پنل"], [CANCEL]])
    try:
        return UI.inline(rows, B, uid)
    except Exception:
        log.exception("partner markup failed")
        return None


async def _login(message, B, UI, uid, st):
    st["mode"] = "p_phone"
    st.pop("phone", None)
    st.pop("partner_active", None)
    markup = None
    try:
        markup = UI.inline([[CANCEL]], B, uid)
    except Exception:
        pass
    kwargs = {"reply_markup": markup} if markup is not None else {}
    return await message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:", **kwargs)


async def _open_partner(update, context, B, UI):
    q = update.callback_query
    if not q or not q.message:
        return
    uid = int(q.from_user.id)
    st = B.S.setdefault(uid, {})
    try:
        if st.get("partner_logged_out"):
            st.pop("partner_id", None); st.pop("partner_active", None)
        pid = st.get("partner_id")
        if pid and st.get("partner_active", True):
            row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            if row:
                st["partner_active"] = True; st["partner_logged_out"] = False; st["mode"] = None
                name = row["name"] or "-"; phone = row["phone"] or "-"; balance = int(row["balance"] or 0)
                markup = _partner_markup(B, UI, uid); kwargs = {"reply_markup": markup} if markup is not None else {}
                return await q.message.reply_text(
                    f"👥 پنل همکاران\n👤 {name}\n📱 {phone}\n💰 اعتبار قابل استفاده: {balance:,} تومان\n\nخدمات فیدای غیرحضوری و سیم کارت از اعتبار همین پنل کسر می‌شود.",
                    **kwargs,
                )
        return await _login(q.message, B, UI, uid, st)
    except Exception:
        log.exception("partner entry failed")
        st["mode"] = "p_phone"
        return await q.message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:")


async def _open_admin(update, context, B):
    q = update.callback_query
    if not q or not q.message:
        return
    uid = int(q.from_user.id)
    if not _is_admin(B, uid):
        return await q.message.reply_text("❌ دسترسی مدیریت ندارید.")
    try:
        import telegram_admin_plus as A
        return await q.message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=A._admin_menu())
    except Exception:
        log.exception("admin entry failed")
        return await q.message.reply_text("🛠 پنل مدیریت در حال آماده‌سازی است. لطفاً دوباره تلاش کنید.")


async def _stable_ui2(update, context, B):
    q = update.callback_query
    if not q or not str(q.data or "").startswith("ui2:"):
        return
    token = str(q.data)[4:]
    try:
        row = B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)).fetchone()
        if not row:
            await q.answer("این گزینه منقضی شده است.", show_alert=True)
            await q.message.reply_text("🔄 منو به‌روزرسانی شد. لطفاً /start را بزنید.")
            raise ApplicationHandlerStop
        if row["user_id"] and str(row["user_id"]) != str(q.from_user.id):
            await q.answer("این گزینه برای کاربر دیگری است.", show_alert=True)
            raise ApplicationHandlerStop
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        if row["lang"]: st["lang"] = row["lang"]
        if row["status"]: st["status"] = row["status"]
        label = str(row["label"] or "").strip()
        aliases = {
            "👥 Partner panel": PARTNER, "👥 لوحة الشركاء": PARTNER,
            "🛠 Admin panel": ADMIN_PANEL, "🛠 لوحة الإدارة": ADMIN_PANEL,
            "🪪 FIDA service": FIDA, "🪪 خدمة فيدا": FIDA,
            "🖨 Printing services": "🖨 خدمات چاپ", "🖨 خدمات الطباعة": "🖨 خدمات چاپ",
            "🪪 Government access help": "🪪 حل مشکل ورود اتباع دولت من", "🪪 مساعدة الدخول الحكومي": "🪪 حل مشکل ورود اتباع دولت من",
            "🎫 Card renewal tracking": "🎫 کد رهگیری تمدید کارت‌ها", "🎫 متابعة تجديد البطاقة": "🎫 کد رهگیری تمدید کارت‌ها",
            "📱 SIM card services": SIM, "📱 خدمات شرائح الهاتف": SIM,
            "📝 Screening test": "📝 آزمون غربالگری", "📝 اختبار الفرز": "📝 آزمون غربالگری",
            "🎫 Track request": "🎫 پیگیری", "🎫 متابعة الطلب": "🎫 پیگیری",
            "💰 My wallet": "💰 کیف پول من", "💰 محفظتي": "💰 کیف پول من",
            "📞 Contact us": "📞 تماس با ما", "📞 اتصل بنا": "📞 تماس با ما",
            "📝 Customer complaints": "📝 ثبت شکایت مشتریان", "📝 شكاوى العملاء": "📝 ثبت شکایت مشتریان",
            "➕ Top up account": "➕ شارژ حساب", "➕ شحن الحساب": "➕ شارژ حساب",
            "🏛 Government access help": "🏛 حل مشکل سامانه دولت من", "🏛 مساعدة الدخول الحكومي": "🏛 حل مشکل سامانه دولت من",
            "🔎 Track code": "🔎 پیگیری کد", "🔎 متابعة الرمز": "🔎 پیگیری کد",
            "📋 History": "📋 سوابق", "📋 السجل": "📋 سوابق",
            "💰 Balance": "💰 موجودی", "💰 الرصيد": "💰 موجودی",
            "🎫 Ticket to admin": "🎫 تیکت به مدیریت", "🎫 تذكرة للإدارة": "🎫 تیکت به مدیریت",
            "🚪 Exit panel": "🚪 خروج از پنل", "🚪 خروج من اللوحة": "🚪 خروج از پنل",
            "❌ Cancel": CANCEL, "❌ إلغاء": CANCEL,
            "🔄 Start again": "🔄 شروع مجدد", "🔄 بدء من جديد": "🔄 شروع مجدد",
        }
        label = aliases.get(label, label)
        from telegram_stable_callback import handle
        await handle(update, context, B, label)
        raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("stable ui2 callback failed label=%r", locals().get("label", ""))
        try: await q.message.reply_text("❌ انجام این گزینه با خطای موقت روبه‌رو شد. منوی اصلی را باز کنید.", reply_markup=B.main(q.from_user.id))
        except Exception: pass
        raise ApplicationHandlerStop


def install():
    import bot as B
    import telegram_ui_policy_v2 as UI
    original = getattr(UI, "_entry_router_original_dispatch", None)
    if original is None:
        original = UI._dispatch
        UI._entry_router_original_dispatch = original
    async def dispatch(update, context, bot_obj, label):
        label = str(label or "").strip()
        if label == PARTNER: return await _open_partner(update, context, bot_obj, UI)
        if label == ADMIN_PANEL: return await _open_admin(update, context, bot_obj)
        return await original(update, context, bot_obj, label)
    UI._dispatch = dispatch
    def partner_kb(lang="fa"):
        uid = UI._uid() or getattr(B, "_ui_current_uid", None) or 0
        return _partner_markup(B, UI, uid)
    B.partner_kb = partner_kb
    B.cancel_kb = lambda lang="fa": UI.inline([[CANCEL]], B, UI._uid() or 0)
    B.partner = lambda update, context: _open_partner_from_message(update, context, B, UI)
    if not getattr(B, "_stable_ui2_handler", False):
        app = getattr(B, "_telegram_application", None)
        if app is not None:
            app.add_handler(CallbackQueryHandler(lambda u, c: _stable_ui2(u, c, B), pattern=r"^ui2:"), group=-11)
            B._stable_ui2_handler = True
    # Final administrative/navigation layer. It is intentionally installed from
    # this last router so no older menu mutation can replace it afterwards.
    try:
        import telegram_admin_power as AP
        AP.install(app, B)
    except Exception:
        log.exception("Telegram admin power layer unavailable")
    log.info("Telegram entry router guard installed")


async def _open_partner_from_message(update, context, B, UI):
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None: return
    uid = int(update.effective_user.id); st = B.S.setdefault(uid, {})
    try:
        if st.get("partner_logged_out"):
            st.pop("partner_id", None); st.pop("partner_active", None)
        pid = st.get("partner_id")
        if pid and st.get("partner_active", True):
            row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            if row:
                st["partner_active"] = True; st["mode"] = None
                markup = _partner_markup(B, UI, uid); kwargs = {"reply_markup": markup} if markup is not None else {}
                return await message.reply_text(
                    f"👥 پنل همکاران\n👤 {row['name'] or '-'}\n📱 {row['phone'] or '-'}\n💰 اعتبار قابل استفاده: {int(row['balance'] or 0):,} تومان\n\nخدمات فیدای غیرحضوری و سیم کارت از اعتبار همین پنل کسر می‌شود.",
                    **kwargs,
                )
        return await _login(message, B, UI, uid, st)
    except Exception:
        log.exception("partner message entry failed")
        st["mode"] = "p_phone"
        return await message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:")
