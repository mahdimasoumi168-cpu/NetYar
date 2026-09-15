"""Final partner-management chat entry guard.

The legacy ui2 callback dispatcher raises ApplicationHandlerStop after entering
management chat. Older callback layers catch that exception as a generic error
and show "اجرای گزینه با خطا مواجه شد". This module handles the management
button before those layers, so pressing the button only enters a waiting state.
No message is sent to management until the partner actually sends content.
"""
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_management_hotfix_v25")
MANAGEMENT_LABELS = {
    "💬 ارتباط با مدیریت",
    "💬 Contact management",
    "💬 التواصل مع الإدارة",
}


def _partner_markup(B, uid):
    try:
        return B.partner_kb(B.S.setdefault(uid, {}).get("lang", "fa"))
    except Exception:
        try:
            import telegram_ui_policy_v2 as UI
            return UI.inline([["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
                             ["📱 خدمات سیم کارت", "🔎 پیگیری کد"],
                             ["📋 سوابق", "💰 موجودی"],
                             ["🎫 تیکت به مدیریت", "💬 ارتباط با مدیریت"],
                             ["🚪 خروج از پنل"], ["❌ انصراف"]], B, uid)
        except Exception:
            return None


def _first_admin(B):
    for source in (getattr(B, "ADM", ()), getattr(B, "ADMINS", ())):
        for value in source or ():
            try:
                return int(value)
            except Exception:
                continue
    return None


def install(app, B):
    if getattr(B, "_partner_management_hotfix_v25", False):
        return

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        token = str(q.data or "")
        if not token.startswith("ui2:"):
            return
        uid = int(q.from_user.id)
        label = ""
        try:
            row = B.db.conn.execute(
                "SELECT user_id,label FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)
            ).fetchone()
            if row and (not row["user_id"] or str(row["user_id"]) == str(uid)):
                label = str(row["label"] or "").strip()
        except Exception:
            log.exception("management hotfix callback lookup failed")

        if not label:
            try:
                markup = getattr(q.message, "reply_markup", None)
                for row in getattr(markup, "inline_keyboard", []) or []:
                    for button in row or []:
                        if str(getattr(button, "callback_data", "")) == token:
                            label = str(getattr(button, "text", "") or "").strip()
                            break
                    if label:
                        break
            except Exception:
                pass

        if label not in MANAGEMENT_LABELS:
            return

        st = B.S.setdefault(uid, {})
        partner_id = st.get("partner_id")
        active = bool(partner_id and st.get("partner_active", False)
                      and not st.get("partner_logged_out", False))
        await q.answer()
        if not active:
            await q.message.reply_text(
                "⛔ ابتدا وارد پنل همکاران شوید.",
                reply_markup=_partner_markup(B, uid),
            )
            raise ApplicationHandlerStop

        admin_id = _first_admin(B)
        if not admin_id:
            await q.message.reply_text(
                "⚠️ ارتباط با مدیریت در حال حاضر مقصد مشخصی ندارد.\n"
                "پنل شما باز است و می‌توانید بعداً دوباره تلاش کنید.",
                reply_markup=_partner_markup(B, uid),
            )
            raise ApplicationHandlerStop

        # Enter a pure waiting state. Do NOT send anything to the admin here;
        # the first actual partner message/media will be forwarded by the
        # existing management destination handler.
        st.update(
            mode="final_partner_chat",
            final_chat_admin=int(admin_id),
            final_chat_partner_id=int(partner_id),
            management_chat_id=int(admin_id),
            chat_reply_pending=False,
        )
        try:
            B.db.set_setting(f"partner_chat_{int(partner_id)}", str(uid))
            B.db.set_setting(f"final_chat_admin_{int(partner_id)}", str(admin_id))
        except Exception:
            log.exception("management hotfix mapping save failed")

        await q.message.reply_text(
            "💬 ارتباط با مدیریت فعال شد.\n\n"
            "حالا پیام خود را ارسال کنید.\n"
            "متن، عکس، فایل، ویس یا ویدیو قابل ارسال است.\n\n"
            "⏳ تا وقتی چیزی ارسال نکنید، هیچ پیامی برای مدیریت فرستاده نمی‌شود.\n"
            "برای پایان ارتباط، «❌ انصراف» را بزنید.",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-80000)
    B._partner_management_hotfix_v25 = True
    log.info("Partner management hotfix v25 installed")
