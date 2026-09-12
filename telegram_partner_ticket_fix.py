"""Final Telegram partner-panel ticket and targeted-message routing guard.

This layer is deliberately installed after every legacy UI/router patch. It
normalizes the partner ticket label, guarantees the button exists in the
partner panel, handles the historical per-request ticket callback, and keeps
administrator replies bound to exactly one selected partner.
"""
import logging
from telegram.ext import ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_ticket_fix")
TICKET_LABELS = {
    "✉️ تیکت به مدیریت",
    "📨 ارسال پیام به مدیریت",
    "✉️ ارسال تیکت به مدیریت",
    "📝 تیکت به مدیریت",
    "Ticket to management",
    "📝 Ticket to management",
}


def _normalize(text):
    text = str(text or "").strip()
    aliases = {
        "✉️ ارسال تیکت به مدیریت": "✉️ تیکت به مدیریت",
        "📨 ارسال پیام به مدیریت": "✉️ تیکت به مدیریت",
        "📝 تیکت به مدیریت": "✉️ تیکت به مدیریت",
        "Ticket to management": "✉️ تیکت به مدیریت",
        "📝 Ticket to management": "✉️ تیکت به مدیریت",
    }
    return aliases.get(text, text)


def install(B):
    if getattr(B, "_partner_ticket_final_fix", False):
        return

    # Force one canonical partner keyboard, while preserving all existing
    # buttons and their order. The ticket entry is placed before exit/cancel.
    original_kb = getattr(B, "partner_kb", None)
    if original_kb:
        def partner_kb(*args, **kwargs):
            markup = original_kb(*args, **kwargs)
            try:
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                if isinstance(markup, InlineKeyboardMarkup):
                    rows = [list(row) for row in markup.inline_keyboard]
                    found = any(_normalize(getattr(b, "text", "")) == "✉️ تیکت به مدیریت" for row in rows for b in row)
                    if not found:
                        insert_at = max(0, len(rows) - 2)
                        rows.insert(insert_at, [InlineKeyboardButton("✉️ تیکت به مدیریت", callback_data="ik:partner-ticket")])
                        markup = InlineKeyboardMarkup(rows)
            except Exception:
                log.exception("could not add partner ticket button")
            return markup
        B.partner_kb = partner_kb

    old_router = B.router

    async def router(update, context):
        message = getattr(update, "effective_message", None) or getattr(update, "message", None)
        uid_obj = getattr(update, "effective_user", None)
        uid = getattr(uid_obj, "id", None)
        text = _normalize(getattr(message, "text", ""))
        st = B.S.setdefault(uid, {}) if uid is not None else {}

        # Ticket entry must work both from an inline button and from legacy
        # text labels. It never changes the selected partner.
        if text == "✉️ تیکت به مدیریت" and st.get("partner_id"):
            st["mode"] = "partner_message"
            await message.reply_text(
                "✉️ تیکت به مدیریت\n\nلطفاً پیام خود را برای مدیریت ارسال کنید.\nمتن، عکس، ویدیو، ویس یا فایل قابل ارسال است.\n\nبرای لغو: ❌ انصراف",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
            raise ApplicationHandlerStop

        # Callback used by the detailed history page. It starts a ticket for
        # the current partner only; the request id is retained for context.
        data = str(getattr(getattr(update, "callback_query", None), "data", "") or "")
        if data.startswith("pr:self:ticket:") and st.get("partner_id"):
            st["mode"] = "ticket_partner_reply"
            try:
                st["ticket_request_id"] = int(data.rsplit(":", 1)[1])
            except Exception:
                st.pop("ticket_request_id", None)
            q = update.callback_query
            await q.answer()
            await q.message.reply_text(
                "✉️ تیکت به مدیریت\n\nپاسخ یا توضیح خود را ارسال کنید.\nمتن، عکس، ویدیو، ویس یا فایل قابل ارسال است.\n\nبرای لغو: ❌ انصراف",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
            raise ApplicationHandlerStop

        # Never broaden an administrator's target. If a partner is selected,
        # the existing ticket handler uses only ticket_partner_id and its chat.
        # This guard intentionally does not call any broadcast/notify function.
        return await old_router(update, context)

    B.router = router
    B._partner_ticket_final_fix = True
