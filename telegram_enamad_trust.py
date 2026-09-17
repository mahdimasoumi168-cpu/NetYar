"""eNAMAD trust/verification entry for the public Telegram menu."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

TRUST_LABEL = "🛡 اعتماد"
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
TRUST_IMAGE_URL = "https://trustseal.enamad.ir/logo.aspx?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
DOMAIN = "netyarmohajer.sizpay.ir"


def _trust_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده نماد اعتماد در eNAMAD", url=TRUST_URL)],
        [InlineKeyboardButton("🌐 مشاهده وب‌سایت پرداخت", url="https://netyarmohajer.sizpay.ir")],
    ])


def _trust_text():
    return (
        "🛡 نماد اعتماد الکترونیکی\n\n"
        "🏢 نام کسب‌وکار: نت یار مهاجر\n"
        "🔤 نام لاتین: NetYareMohajer\n"
        f"🌐 دامنه: {DOMAIN}\n"
        "☎️ تلفن: 03135674350\n"
        "📧 ایمیل: netyaremohajer@gmail.com\n\n"
        "این بخش برای مشاهده و بررسی نماد اعتماد الکترونیکی کسب‌وکار است."
    )


def _add_reply_button(markup):
    if not isinstance(markup, ReplyKeyboardMarkup):
        return markup
    rows = [list(row) for row in markup.keyboard]
    if any(TRUST_LABEL in [getattr(b, "text", str(b)) for b in row] for row in rows):
        return markup
    # Keep the public menu compact and place اعتماد immediately before cancel.
    cancel_idx = next((i for i, row in enumerate(rows) if any(getattr(b, "text", str(b)) == "❌ انصراف" for b in row)), len(rows))
    rows.insert(cancel_idx, [TRUST_LABEL])
    return ReplyKeyboardMarkup(rows, resize_keyboard=markup.resize_keyboard, one_time_keyboard=markup.one_time_keyboard, selective=markup.selective, input_field_placeholder=markup.input_field_placeholder, is_persistent=getattr(markup, "is_persistent", None))


def _add_inline_button(markup):
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    rows = [list(row) for row in markup.inline_keyboard]
    if any(any(getattr(b, "text", "") == TRUST_LABEL for b in row) for row in rows):
        return markup
    rows.append([InlineKeyboardButton(TRUST_LABEL, callback_data="enamad:trust")])
    return InlineKeyboardMarkup(rows)


async def install(app, B):
    if getattr(B, "_enamad_trust_installed", False):
        return True

    original_main = B.main

    def main(uid):
        try:
            markup = original_main(uid)
            return _add_inline_button(_add_reply_button(markup))
        except Exception:
            return original_main(uid)

    B.main = main

    async def callback(update, context):
        q = update.callback_query
        if not q or str(q.data or "") != "enamad:trust":
            return
        await q.answer()
        await q.message.reply_text(_trust_text(), reply_markup=_trust_markup(), disable_web_page_preview=True)

    async def text(update, context):
        if not update.message or (update.message.text or "").strip() != TRUST_LABEL:
            return
        await update.message.reply_text(_trust_text(), reply_markup=_trust_markup(), disable_web_page_preview=True)

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^enamad:trust$"), group=-20050)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-20049)
    B._enamad_trust_installed = True
    return True
