"""Final messenger stability layer.

Goals:
- Telegram must use inline buttons only; never recreate a ReplyKeyboard below the chat.
- Remove any legacy Telegram reply keyboard whenever /start is used.
- Put the final ik:* callback router before older compatibility handlers so buttons do not jump.
- Keep Rubika on its already-working ReceiveUpdate path and harden outbound sends without
  starting a second polling consumer when webhook traffic is already arriving.
"""
import asyncio
import logging
import threading
import time

log = logging.getLogger("netyar.messenger_final_stability")

try:
    from telegram import Bot, ReplyKeyboardMarkup, ReplyKeyboardRemove
    from telegram.ext import CallbackQueryHandler
    import bot as B

    if not getattr(B, "_messenger_final_telegram_installed", False):
        _old_send_message = Bot.send_message

        async def _send_message_no_reply_keyboard(self, *args, **kwargs):
            rm = kwargs.get("reply_markup")
            if isinstance(rm, ReplyKeyboardMarkup):
                kwargs["reply_markup"] = None
            return await _old_send_message(self, *args, **kwargs)

        Bot.send_message = _send_message_no_reply_keyboard

        async def _remove_reply_keyboard_every_time(message):
            try:
                if message is None:
                    return
                sent = await message.reply_text("\u2063", reply_markup=ReplyKeyboardRemove())
                try:
                    await sent.delete()
                except Exception:
                    pass
            except Exception:
                pass

        _old_start = B.start

        async def _final_start(update, context):
            msg = getattr(update, "effective_message", None)
            await _remove_reply_keyboard_every_time(msg)
            return await _old_start(update, context)

        B.start = _final_start

        async def _final_ik_router(update, context):
            q = getattr(update, "callback_query", None)
            if q is None:
                return
            data = str(getattr(q, "data", "") or "")
            if not data.startswith("ik:"):
                return
            try:
                await q.answer()
            except Exception:
                pass
            try:
                import final_platform_fix as P
                label = P._actions.get(data)
                if label is None:
                    try:
                        await q.message.reply_text("این گزینه منقضی شده؛ لطفاً منوی جدید را انتخاب کنید.")
                    except Exception:
                        pass
                    return
                original = getattr(q.message, "text", None)
                try:
                    object.__setattr__(q.message, "text", str(label))
                    await B.router(update, context)
                finally:
                    try:
                        object.__setattr__(q.message, "text", original)
                    except Exception:
                        pass
            except Exception:
                log.exception("final Telegram ik router failed")
                try:
                    await q.message.reply_text("❌ اجرای گزینه با خطا مواجه شد. لطفاً دوباره تلاش کنید.")
                except Exception:
                    pass

        _old_build = B.build

        def _final_build():
            app = _old_build()
            app.add_handler(CallbackQueryHandler(_final_ik_router, pattern=r"^ik:"), group=-100)
            return app

        B.build = _final_build
        B._messenger_final_telegram_installed = True
        log.info("Messenger final: Telegram reply keyboards disabled and ik router prioritized")
except Exception:
    log.exception("Messenger final Telegram layer failed")

try:
    import rubika_v2 as RB

    if not getattr(RB, "_messenger_final_rubika_installed", False):
        _send_lock = threading.Lock()
        _last_send = 0.0
        _original_send = RB.send

        def _paced_original_send(chat, text, rows=None):
            global _last_send
            with _send_lock:
                gap = 2.2 - (time.monotonic() - _last_send)
                if gap > 0:
                    time.sleep(gap)
                last_error = None
                for attempt in range(4):
                    try:
                        result = _original_send(chat, text, rows)
                        _last_send = time.monotonic()
                        if isinstance(result, dict) and result.get("status") == "TOO_REQUESTS":
                            raise RuntimeError("TOO_REQUESTS")
                        return result
                    except Exception as exc:
                        last_error = exc
                        if attempt >= 3:
                            break
                        time.sleep(min(15.0, 3.0 * (attempt + 1)))
                log.error("Rubika outbound send failed after retries: %s", last_error)
                return {"status": "RETRY_LATER", "error": str(last_error or "send failed")}

        RB.send = _paced_original_send
        RB._messenger_final_rubika_installed = True
        log.info("Messenger final: Rubika outbound rate/retry guard installed")
except Exception:
    log.exception("Messenger final Rubika layer failed")
