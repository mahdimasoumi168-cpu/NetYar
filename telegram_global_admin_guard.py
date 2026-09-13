"""High-priority Telegram admin callback owner.

Admin callbacks must be consumed exactly once. A legacy admin handler may throw
or fall through after sending a successful response, which used to create the
visible `error` + `success` double response. This guard owns adm:* callbacks and
turns real failures into one contextual error without returning to the main menu.
"""
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.global_admin_guard")


def install(app, B):
    if getattr(B, "_global_admin_guard", False):
        return True

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q:
            return
        data = str(q.data or "")
        if not data.startswith("adm:") or not B.admin(q.from_user.id):
            return
        try:
            await q.answer()
        except Exception:
            pass
        try:
            import telegram_admin_plus as A
            await A._callback(update, context, B)
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("admin callback failed: %s", data)
            uid = q.from_user.id
            st = B.S.setdefault(uid, {"admin": True})
            st["admin_plus_mode"] = st.get("admin_plus_mode")
            try:
                await q.message.reply_text(
                    "❌ اجرای این بخش با خطای موقت مواجه شد.\n"
                    "وضعیت فعلی پنل مدیریت حفظ شد؛ لطفاً دوباره همین گزینه را بزنید.",
                    reply_markup=B.amenu(),
                )
            except Exception:
                pass
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^adm:"), group=-65000)
    B._global_admin_guard = True
    return True
