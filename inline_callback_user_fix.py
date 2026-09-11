"""Fix Telegram inline callback ownership errors from shared menu state."""
import logging

log = logging.getLogger("netyar.inline_callback_user_fix")


def install():
    import bot as B
    import final_ui_flow_patch as F

    if getattr(B, "_inline_callback_user_fix_installed", False):
        return

    async def callback(update, context):
        q = update.callback_query
        await q.answer()
        entry = F._UI.get(str(q.data or ""))
        if not entry:
            return await q.message.reply_text(
                "❌ این گزینه منقضی شده است. لطفاً منو را دوباره باز کنید."
            )

        # The token's old owner was taken from a process-global menu variable.
        # That is unsafe with concurrent users and caused the exact error shown
        # in the screenshot. The Telegram callback sender is the real owner.
        _old_owner, label = entry
        fake = F._fake_update(update, label)
        try:
            result = await B.router(fake, context)
            if result is None:
                if await B.ptext(fake, context):
                    return
                await B.service_text(fake, context)
        except Exception:
            log.exception("inline callback failed: %s", label)
            await q.message.reply_text("❌ در اجرای این گزینه خطایی رخ داد. دوباره تلاش کنید.")

    # final_ui_flow_patch's build looks up F._ui_callback when it builds the
    # application, so replacing the function here is enough and avoids adding
    # duplicate callback handlers.
    F._ui_callback = callback
    B._inline_callback_user_fix_installed = True
    log.info("inline callback ownership fix installed")
