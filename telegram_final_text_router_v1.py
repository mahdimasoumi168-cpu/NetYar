"""Deterministic final owner for Telegram reply-keyboard buttons.

Reply-keyboard buttons arrive as ordinary text messages, so callback owners do
not protect them. This layer is installed last and consumes only exact menu
labels while leaving active data-entry states untouched.
"""
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

MARK = "_telegram_final_text_router_v1"
ADMIN = {"🛠 پنل مدیریت بات", "🛠 پنل مدیریت", "پنل مدیریت بات", "پنل مدیریت"}
PARTNER = {"👥 پنل همکاران", "🔵 👥 پنل همکاران", "👥 Partner panel", "👥 لوحة الشركاء"}
KNOWN = {
    "➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من", "🔎 پیگیری کد", "📋 سوابق",
    "💰 موجودی", "💰 کیف پول من", "🪪 فیدای غیر حضوری", "🖨 خدمات چاپ",
    "🪪 حل مشکل ورود اتباع دولت من", "📱 خدمات سیم کارت", "🎫 پیگیری",
    "📞 تماس با ما", "📝 ثبت شکایت مشتریان", "💬 ارتباط با مدیریت",
    "🚪 خروج از پنل", "❌ انصراف", "🔄 شروع مجدد", "🔄 شروع دوباره",
}
ALIASES = {"🔵 👥 پنل همکاران":"👥 پنل همکاران", "👥 Partner panel":"👥 پنل همکاران", "👥 لوحة الشركاء":"👥 پنل همکاران"}


def _in_data_entry(st):
    mode = str(st.get("mode") or "")
    return mode not in {"", "main", "partner_panel", "p_logged", "p_menu", "public_menu"}


async def _partner(update, context, B):
    uid = update.effective_user.id
    st = B.S.setdefault(uid, {})
    if st.get("partner_logged_out"):
        st.pop("partner_id", None); st.pop("partner_active", None)
    pid = st.get("partner_id")
    if pid and st.get("partner_active", True):
        row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
        if row:
            st["partner_active"] = True; st["partner_logged_out"] = False; st["mode"] = None
            return await update.effective_message.reply_text(
                f"👥 پنل همکاران\n👤 {row['name'] or '-'}\n📱 {row['phone'] or '-'}\n💰 اعتبار: {int(row['balance'] or 0):,} تومان",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )
    st["mode"]="p_phone"; st["step"]="partner_phone"
    st.pop("phone",None); st.pop("partner_phone",None); st.pop("partner_id",None); st.pop("partner_active",None)
    return await update.effective_message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang","fa")))


async def _route(update, context, B):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not msg.text:
        return
    text = str(msg.text).strip()
    uid = user.id
    st = B.S.setdefault(uid, {})
    # Never steal an ordinary text value while a service is collecting input.
    if _in_data_entry(st):
        return
    if text in ADMIN:
        if not B.admin(uid):
            return
        try:
            import telegram_admin_plus as A
            st["admin_plus_mode"] = None
            await msg.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=A._admin_menu())
        except Exception:
            await msg.reply_text("❌ پنل مدیریت موقتاً در دسترس نیست.")
        raise ApplicationHandlerStop
    text = ALIASES.get(text, text)
    if text in PARTNER or text == "👥 پنل همکاران":
        await _partner(update, context, B)
        raise ApplicationHandlerStop
    if text not in KNOWN:
        return
    # Direct feature calls are deterministic and avoid competing legacy text handlers.
    direct = {
        "➕ شارژ حساب":"topup", "🏛 حل مشکل سامانه دولت من":"gov", "🪪 حل مشکل ورود اتباع دولت من":"gov",
        "🔎 پیگیری کد":"ptrack", "📋 سوابق":"phistory", "🪪 فیدای غیر حضوری":"fida", "🖨 خدمات چاپ":"prt",
        "📱 خدمات سیم کارت":"sim_start", "💰 کیف پول من":"customer_wallet",
    }
    if text in {"❌ انصراف", "🔄 شروع مجدد", "🔄 شروع دوباره"}:
        fn = getattr(B, "cancel" if text == "❌ انصراف" else "start", None)
        if fn:
            await fn(update, context)
            raise ApplicationHandlerStop
    if text == "🎫 پیگیری":
        st["mode"]="public_tracking"
        await msg.reply_text("🎫 کد پیگیری را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang","fa")))
        raise ApplicationHandlerStop
    if text == "📞 تماس با ما":
        # Let the established router own this label if available.
        fn=getattr(B,"router",None)
        if fn:
            result=await fn(update,context)
            if result is not None: raise ApplicationHandlerStop
    if text == "📝 ثبت شکایت مشتریان":
        st["mode"]="ui2_complaint"
        await msg.reply_text("📝 ثبت شکایت مشتریان\n\nمتن شکایت یا انتقاد خود را ارسال کنید:", reply_markup=B.cancel_kb(st.get("lang","fa")))
        raise ApplicationHandlerStop
    fn = getattr(B, direct.get(text,""), None)
    if fn:
        await fn(update, context)
        raise ApplicationHandlerStop
    fn = getattr(B, "router", None)
    if fn:
        result = await fn(update, context)
        if result is not None:
            raise ApplicationHandlerStop
    await msg.reply_text("❌ این گزینه در حال حاضر در دسترس نیست.", reply_markup=B.partner_kb(st.get("lang","fa")) if st.get("partner_id") else B.main(uid))
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, MARK, False):
        return
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: _route(u,c,B)), group=-7000000)
    setattr(B, MARK, True)
