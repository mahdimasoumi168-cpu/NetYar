"""Fix inline Telegram callback ownership errors caused by shared menu state.

Inline button tokens are UI labels, not authorization credentials. The callback
must execute against the user who actually clicked the button. Older code bound
tokens to a process-global menu owner, which can become stale when menus are
created for another user and produced: «این دکمه برای کاربر دیگری است.»
"""
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

        # Do NOT compare against the process-global owner stored when the
        # keyboard was built. Multiple users can create menus concurrently.
        # The actual Telegram user/chat in this callback is the execution owner.
        _owner, label = entry
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

    # The handler already points at F._ui_callback by function object, so patch
    # the function before any subsequent build; then replace the installed
    # handler registration with a small wrapper in telegram_runtime.build.
    F._ui_callback = callback
    old_build = F.TG.build if hasattr(F, "TG") else None
    if old_build is None:
        # final_ui_flow_patch keeps TG as a local; register directly on the
        # telegram runtime builder by rebuilding its app after the existing
        # builder has run.
        import telegram_runtime as TG
        old_tg_build = TG.build
        from telegram import CallbackQueryHandler

        def build():
            app = old_tg_build()
            app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui:"))
            return app

        TG.build = build
    else:
        F.TG.build = old_build

    B._inline_callback_user_fix_installed = True
    log.info("inline callback ownership fix installed")
