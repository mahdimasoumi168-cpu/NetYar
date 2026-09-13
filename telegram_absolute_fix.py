"""Canonical Telegram callback/navigation owner."""
import logging
from types import SimpleNamespace
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.absolute_fix")

ALIASES = {
    "🔷 👥 پنل همکاران": "👥 پنل همکاران", "👥 Partner panel": "👥 پنل همکاران", "👥 لوحة الشركاء": "👥 پنل همکاران",
    "🔷 🛠 پنل مدیریت بات": "🛠 پنل مدیریت بات", "🛠 Admin panel": "🛠 پنل مدیریت بات", "🛠 لوحة الإدارة": "🛠 پنل مدیریت بات",
    "🔷 ➕ شارژ حساب": "➕ شارژ حساب", "🔷 🏛 حل مشکل سامانه دولت من": "🏛 حل مشکل سامانه دولت من",
    "🔷 🔎 پیگیری کد": "🔎 پیگیری کد", "🔷 📋 سوابق": "📋 سوابق", "🔷 💰 موجودی": "💰 موجودی", "🔷 🚪 خروج از پنل": "🚪 خروج از پنل",
    "📨 ارسال پیام به مدیریت": "✉️ تیکت به مدیریت", "✉️ ارسال تیکت به مدیریت": "✉️ تیکت به مدیریت", "📝 تیکت به مدیریت": "✉️ تیکت به مدیریت",
    "🔄 شروع دوباره": "🔄 شروع مجدد", "Start again": "🔄 شروع مجدد", "Restart": "🔄 شروع مجدد",
    "🪪 FIDA service": "🪪 فیدای غیر حضوری", "🖨 Printing": "🖨 خدمات چاپ", "🏛 Government access": "🪪 حل مشکل ورود اتباع دولت من",
    "🎫 Card renewal tracking": "🎫 کد رهگیری تمدید کارت‌ها", "📱 SIM services": "📱 خدمات سیم کارت", "📝 Screening test": "📝 آزمون غربالگری",
    "🎫 Tracking": "🎫 پیگیری", "💰 My wallet": "💰 کیف پول من", "📞 Contact us": "📞 تماس با ما", "📝 Customer complaint": "📝 ثبت شکایت مشتریان",
}

def clean(value):
    text = str(value or "").strip()
    for prefix in ("🟢 ", "🟠 ", "🟣 ", "🟡 ", "⚪ ", "🔷 ", "🟦 ", "🟩 ", "🟨 ", "🔵 "):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return ALIASES.get(text, text)

def _label(query):
    try:
        import telegram_no_reply_keyboard as keyboard
        value = keyboard._ACTIONS.get(str(query.data))
        if value: return clean(value)
    except Exception: pass
    try:
        markup = getattr(query.message, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", []) or []:
            for button in row:
                if str(getattr(button, "callback_data", "")) == str(query.data):
                    return clean(getattr(button, "text", ""))
    except Exception:
        log.exception("cannot recover Telegram button label")
    return ""

def _proxy(update, query, text):
    source = query.message
    class MessageProxy:
        def __init__(self, original, value): self._original, self.text = original, value
        def __getattr__(self, name): return getattr(self._original, name)
    message = MessageProxy(source, text)
    return SimpleNamespace(update_id=getattr(update, "update_id", None), message=message, effective_message=message,
                           effective_user=query.from_user, effective_chat=getattr(source, "chat", None), callback_query=query)

async def _button_text_guard(update, context, B):
    """Reply-keyboard control buttons must never become ticket/message content."""
    message = update.effective_message
    if not message or not getattr(message, "text", None): return
    text = str(message.text).strip()
    uid = update.effective_user.id
    if text in {"🔄 شروع مجدد", "🔄 شروع دوباره", "Restart", "Start again"}:
        old = dict(B.S.setdefault(uid, {})); B.S[uid] = {"lang": old.get("lang", "fa")}
        status = old.get("status") or old.get("citizenship")
        if status: B.S[uid].update(status=status, citizenship=status)
        await B.start(update, context)
        raise ApplicationHandlerStop
    if text in {"❌ انصراف", "❌ Cancel", "❌ إلغاء", "لغو", "انصراف"}:
        await B.cancel(update, context)
        raise ApplicationHandlerStop
    if text == "➕ افزودن همکار" and B.admin(uid):
        try:
            import admin_full_v6
            await admin_full_v6.admin_text(update, context)
        except Exception:
            B.S.setdefault(uid, {})["mode"] = "admin_add_partner"
            await message.reply_text("➕ افزودن همکار\n\nفرمت:\nشماره | رمز | نام همکار\nمثال: 09xxxxxxxxx | رمز جدید | همکار اصفهان", reply_markup=B.cancel_kb())
        raise ApplicationHandlerStop

def _admin_menu(B):
    try:
        import telegram_admin_plus as A
        return A._admin_menu()
    except Exception:
        try: return B.amenu()
        except Exception: return None

async def click(update, context, B):
    query = update.callback_query
    if not query: return
    await query.answer()
    text = _label(query); uid = query.from_user.id; state = B.S.setdefault(uid, {})
    if not text:
        await query.message.reply_text("⛔ این گزینه دیگر معتبر نیست؛ لطفاً از منوی فعلی استفاده کنید."); raise ApplicationHandlerStop
    try:
        if text == "🔄 شروع مجدد":
            old = dict(state); B.S[uid] = {"lang": old.get("lang", "fa")}
            status = old.get("status") or old.get("citizenship")
            if status: B.S[uid].update(status=status, citizenship=status)
            await B.start(_proxy(update, query, "/start"), context); raise ApplicationHandlerStop
        if text == "❌ انصراف":
            await B.cancel(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "👥 پنل همکاران":
            await B.partner(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "🛠 پنل مدیریت بات":
            if not B.admin(uid): await query.message.reply_text("⛔ این بخش فقط برای مدیریت فعال است.")
            else:
                try:
                    import telegram_admin_plus as admin_plus
                    state["admin"] = True; state["mode"] = None; state["admin_plus_mode"] = None
                    await query.message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=admin_plus._admin_menu())
                except Exception:
                    fn = getattr(B, "admin_text", None)
                    if fn: await fn(_proxy(update, query, text), context)
                    else: await query.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            raise ApplicationHandlerStop
        if text == "📱 خدمات سیم کارت":
            fn = getattr(B, "sim_start", None)
            if fn: await fn(_proxy(update, query, text), context)
            else: await query.message.reply_text("⛔ خدمات سیم کارت فعلاً در دسترس نیست.")
            raise ApplicationHandlerStop
        if text == "🪪 فیدای غیر حضوری":
            await B.fida(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "🖨 خدمات چاپ":
            await B.prt(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "🪪 حل مشکل ورود اتباع دولت من":
            await B.gov(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "🚪 خروج از پنل":
            await B.partner_exit(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "📋 سوابق":
            await B.phistory(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "🔎 پیگیری کد":
            await B.ptrack(_proxy(update, query, text), context); raise ApplicationHandlerStop
        if text == "💰 موجودی":
            partner_id = state.get("partner_id"); row = B.db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1", (partner_id,)).fetchone()
            await query.message.reply_text(f"💰 موجودی شما: {int(row['balance'] or 0):,} تومان" if row else "⛔ حساب همکار فعال نیست.", reply_markup=B.partner_kb(state.get("lang", "fa"))); raise ApplicationHandlerStop
        if text == "➕ شارژ حساب":
            fn = getattr(B, "topup", None)
            if fn: await fn(_proxy(update, query, text), context)
            else: await query.message.reply_text("⛔ شارژ حساب فعلاً در دسترس نیست.", reply_markup=B.partner_kb(state.get("lang", "fa")))
            raise ApplicationHandlerStop
        if text == "✉️ تیکت به مدیریت":
            if not state.get("partner_id"): await query.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.")
            else:
                state["mode"] = "partner_message"
                await query.message.reply_text("✉️ تیکت به مدیریت\n\nلطفاً پیام خود را برای مدیریت ارسال کنید.\nبرای لغو، دکمه «❌ انصراف» را بزنید.", reply_markup=B.cancel_kb(state.get("lang", "fa")))
            raise ApplicationHandlerStop
        result = await B.router(_proxy(update, query, text), context)
        if result is None: await query.message.reply_text("⛔ این گزینه فعلاً در دسترس نیست. لطفاً از منوی فعلی استفاده کنید.", reply_markup=B.main(uid))
    except ApplicationHandlerStop: raise
    except Exception:
        log.exception("canonical Telegram callback failed: %s", text)
        await query.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
    raise ApplicationHandlerStop

def install(app, B):
    if getattr(B, "_telegram_absolute_fix", False): return
    def main(uid):
        rows = [["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"], ["🪪 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها"],
                ["📱 خدمات سیم کارت", "📝 آزمون غربالگری و پیگیری"], ["🎫 پیگیری", "💰 کیف پول من"], ["📞 تماس با ما", "📝 ثبت شکایت مشتریان"]]
        if B.admin(uid): rows.append(["🛠 پنل مدیریت بات"])
        rows.append(["👥 پنل همکاران"]); return B.kb(rows)
    def partner_kb(lang="fa"):
        return B.kb([["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🪪 فیدای غیر حضوری", "📱 خدمات سیم کارت"],
                     ["🔎 پیگیری کد", "📋 سوابق"], ["💰 موجودی"], ["✉️ تیکت به مدیریت"], ["🚪 خروج از پنل"]])
    B.main = main; B.partner_kb = partner_kb
    app.add_handler(CallbackQueryHandler(lambda update, context: click(update, context, B), pattern=r"^ik:"), group=-4000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: _button_text_guard(update, context, B)), group=-3999)
    B._telegram_absolute_fix = True
    log.info("Canonical Telegram callback/navigation owner installed")
