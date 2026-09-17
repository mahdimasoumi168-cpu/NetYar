"""Authoritative manager -> ordinary subscriber security-code flow.

A manager can request a numeric code from the exact Telegram account that
created a customer request. The reply is returned to the same manager and is
bound to the same request id.
"""
import logging
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.customer_code_request")


def install(app, B):
    if getattr(B, "_customer_code_request_v1", False):
        return True

    try:
        app.add_handler(CallbackQueryHandler(_callback_factory(B), pattern=r"^req:c:\d+$"), group=-8999997)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _text_factory(B)), group=-8999996)
        B._customer_code_request_v1 = True
        log.info("Customer security-code workflow installed")
        return True
    except Exception:
        log.exception("Customer security-code workflow install failed")
        return False


def _request(B, rid):
    try:
        return B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1", (rid,)).fetchone()
    except Exception:
        return None


def _requester_chat(B, rid, row):
    # Prefer the canonical request chat mapping, then the request owner.
    try:
        import request_language_actions as L
        x = L.request_chat(B.db, rid)
        if x is not None and str(x).strip().lstrip("-").isdigit():
            return int(x)
    except Exception:
        pass
    try:
        x = str(B.db.setting(f"request_chat_{rid}", "") or "").strip()
        if x.lstrip("-").isdigit():
            return int(x)
    except Exception:
        pass
    try:
        x = str(row["user_id"] or "").strip()
        if x.lstrip("-").isdigit():
            return int(x)
    except Exception:
        pass
    return None


def _callback_factory(B):
    async def callback(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id):
            return
        try:
            rid = int(str(q.data).split(":")[-1])
        except Exception:
            return
        row = _request(B, rid)
        if not row:
            await q.answer("❌ درخواست پیدا نشد.", show_alert=True)
            raise ApplicationHandlerStop
        chat = _requester_chat(B, rid, row)
        if not chat:
            await q.answer("❌ حساب مشترک این درخواست پیدا نشد.", show_alert=True)
            raise ApplicationHandlerStop

        # Bind the exact manager and request to the requester chat.
        B.db.set_setting(f"customer_code_admin_{rid}", str(q.from_user.id))
        B.db.set_setting(f"customer_code_chat_{rid}", str(chat))
        try:
            B.db.conn.execute(
                "UPDATE requests SET status='awaiting_customer_code',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
        except Exception:
            log.exception("Could not update customer code status rid=%s", rid)

        st = B.S.setdefault(chat, {})
        st.update(mode="customer_security_code", customer_code_rid=rid,
                  customer_code_admin=str(q.from_user.id), lang="fa")
        tracking = str(row["tracking_code"] or rid)
        await q.answer("📨 درخواست کد برای مشترک ارسال شد.")
        await context.bot.send_message(
            chat_id=chat,
            text=(f"🔐 درخواست کد از مدیریت\n\n🎫 کد پیگیری: {tracking}\n"
                  "لطفاً کد عددی اعلام‌شده برای این درخواست را فقط در همین چت ارسال کنید."),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ انصراف", callback_data=f"customer_code:cancel:{rid}")]
            ]),
        )
        await q.message.reply_text(
            f"📨 درخواست کد برای مشترک ارسال شد.\n🎫 {tracking}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
                [InlineKeyboardButton("🔐 درخواست مجدد کد از مشترک", callback_data=f"req:c:{rid}")],
                [InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
            ]),
        )
        raise ApplicationHandlerStop
    return callback


def _text_factory(B):
    async def handler(update, context):
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user:
            return
        st = B.S.get(user.id, {}) or {}
        if st.get("mode") != "customer_security_code":
            return
        text = str(msg.text or "").strip()
        if not re.fullmatch(r"\d{3,20}", text):
            await msg.reply_text("❌ کد باید فقط عددی باشد. لطفاً کد را دوباره ارسال کنید.")
            raise ApplicationHandlerStop
        rid = int(st.get("customer_code_rid"))
        admin = int(st.get("customer_code_admin"))
        row = _request(B, rid)
        if not row:
            st.clear()
            await msg.reply_text("❌ این درخواست دیگر معتبر نیست.")
            raise ApplicationHandlerStop
        tracking = str(row["tracking_code"] or rid)
        try:
            B.db.answer(rid, "customer_security_code", answer=text)
            B.db.conn.execute(
                "UPDATE requests SET status='customer_code_received',updated_at=? WHERE id=?",
                (B.now(), rid),
            )
            B.db.conn.commit()
        except Exception:
            log.exception("Could not persist customer code rid=%s", rid)
        try:
            await context.bot.send_message(
                chat_id=admin,
                text=f"🔐 کد مشترک دریافت شد\n\n🎫 کد پیگیری: {tracking}\n🔢 کد: {text}\n👤 حساب مشترک: {user.id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
                    [InlineKeyboardButton("✉️ پاسخ به مشترک", callback_data=f"req:r:{rid}")],
                    [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
                ]),
            )
        except Exception:
            log.exception("Could not return customer code to manager rid=%s", rid)
        st.pop("mode", None); st.pop("customer_code_rid", None); st.pop("customer_code_admin", None)
        await msg.reply_text("✅ کد شما با موفقیت برای مدیریت ارسال شد.")
        raise ApplicationHandlerStop
    return handler
