"""Final Telegram runtime repair layer.

This layer is intentionally small and authoritative: it runs before legacy
catch-all handlers so requested actions reach the correct feature instead of
being swallowed by generic callbacks.
"""
import re
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.final_runtime_repair")

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def _digits(v):
    return str(v or "").translate(DIGITS)

def install(app, B):
    if getattr(B, "_final_runtime_repair_v1", False):
        return True

    # The customer-code callback must run before bot.py's broad req:* owner.
    try:
        import telegram_customer_code_request_v1 as C
        app.add_handler(CallbackQueryHandler(C._callback_factory(B), pattern=r"^req:c:\d+$"), group=-1000000)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, C._text_factory(B)), group=-999999)
        log.info("FINAL REPAIR: customer-code owner installed before generic req handler")
    except Exception:
        log.exception("FINAL REPAIR: customer-code owner unavailable")

    # Add the requested 'افزودن همکار' action to the authoritative admin menu.
    try:
        import telegram_admin_plus as A
        original_menu = A._admin_menu
        if not getattr(A, "_final_add_partner_menu_v1", False):
            def admin_menu_with_partner():
                base = original_menu()
                rows = [list(r) for r in base.inline_keyboard]
                # Keep one deterministic button; do not duplicate it on reload.
                if not any((b.text == "➕ افزودن همکار") for r in rows for b in r):
                    rows.insert(1, [InlineKeyboardButton("➕ افزودن همکار", callback_data="adm:addpartner")])
                return InlineKeyboardMarkup(rows)
            A._admin_menu = admin_menu_with_partner
            A._final_add_partner_menu_v1 = True
            B.amenu = A._admin_menu

        async def add_partner_callback(update, context):
            q = update.callback_query
            if not q or q.data != "adm:addpartner":
                return
            if not B.admin(q.from_user.id):
                await q.answer("❌ دسترسی مدیریت ندارید.", show_alert=True)
                raise ApplicationHandlerStop
            st = B.S.setdefault(q.from_user.id, {})
            st["final_add_partner"] = "name"
            await q.answer()
            await q.message.reply_text("➕ افزودن همکار\n\n👤 نام و نام خانوادگی همکار را وارد کنید:")
            raise ApplicationHandlerStop

        async def add_partner_text(update, context):
            msg = update.effective_message
            uid = update.effective_user.id if update.effective_user else None
            if not msg or uid is None or not B.admin(uid):
                return
            st = B.S.setdefault(uid, {})
            mode = st.get("final_add_partner")
            if not mode:
                return
            text = str(msg.text or "").strip()
            if text in {"❌ انصراف", "لغو", "انصراف"}:
                st.pop("final_add_partner", None)
                await msg.reply_text("❌ عملیات لغو شد.", reply_markup=A._admin_menu())
                raise ApplicationHandlerStop
            if mode == "name":
                if len(text) < 2:
                    await msg.reply_text("❌ نام معتبر وارد کنید.")
                    raise ApplicationHandlerStop
                st["final_partner_name"] = text
                st["final_add_partner"] = "phone"
                await msg.reply_text("📱 شماره موبایل همکار را وارد کنید:")
                raise ApplicationHandlerStop
            if mode == "phone":
                phone = re.sub(r"\D", "", _digits(text))
                if phone.startswith("98"): phone = "0" + phone[2:]
                if not re.fullmatch(r"09\d{9}", phone):
                    await msg.reply_text("❌ شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.")
                    raise ApplicationHandlerStop
                if B.db.conn.execute("SELECT 1 FROM partners WHERE phone=?", (phone,)).fetchone():
                    await msg.reply_text("❌ این شماره قبلاً به عنوان همکار ثبت شده است.")
                    raise ApplicationHandlerStop
                st["final_partner_phone"] = phone
                st["final_add_partner"] = "password"
                await msg.reply_text("🔐 رمز ورود همکار را وارد کنید (حداقل ۴ کاراکتر):")
                raise ApplicationHandlerStop
            if mode == "password":
                if len(text) < 4:
                    await msg.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.")
                    raise ApplicationHandlerStop
                from core import hash_password
                B.db.conn.execute(
                    "INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (st["final_partner_phone"], hash_password(text), st["final_partner_name"], 1, 0, B.now(), B.now()),
                )
                B.db.conn.commit()
                row = B.db.conn.execute("SELECT id FROM partners WHERE phone=?", (st["final_partner_phone"],)).fetchone()
                name, phone = st["final_partner_name"], st["final_partner_phone"]
                for k in ("final_add_partner", "final_partner_name", "final_partner_phone"):
                    st.pop(k, None)
                await msg.reply_text(
                    f"✅ همکار با موفقیت اضافه شد.\n\n👤 {name}\n📱 {phone}\n🆔 شناسه: {row['id'] if row else '-'}\n💰 موجودی اولیه: 0 تومان",
                    reply_markup=A._admin_menu(),
                )
                raise ApplicationHandlerStop

        app.add_handler(CallbackQueryHandler(add_partner_callback, pattern=r"^adm:addpartner$"), group=-1000001)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_partner_text), group=-1000002)
    except Exception:
        log.exception("FINAL REPAIR: admin partner creation unavailable")

    B._final_runtime_repair_v1 = True
    return True
