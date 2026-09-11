"""Final platform hardening: inline-only UI, callback-safe routing, Rubika rate limiting."""
import logging
import threading
import time
from collections import OrderedDict

log = logging.getLogger("netyar.final_platform_fix")

# ---------------- Telegram ----------------
try:
    import bot as B
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
    from telegram.ext import CallbackQueryHandler

    _actions = OrderedDict()
    _seq = 0
    _lock = threading.Lock()
    _removed_chats = set()

    def _remember(label):
        global _seq
        with _lock:
            _seq += 1
            key = f"ik:{_seq}"
            _actions[key] = str(label)
            while len(_actions) > 2000:
                _actions.popitem(last=False)
        return key

    def inline_kb(rows):
        out = []
        for row in rows or []:
            buttons = []
            for item in row or []:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    label = str(item[1])
                else:
                    label = str(item)
                if label:
                    buttons.append(InlineKeyboardButton(label, callback_data=_remember(label)))
            if buttons:
                out.append(buttons)
        return InlineKeyboardMarkup(out)

    # Make every existing kb() helper in bot.py produce inline buttons.
    B.kb = inline_kb
    B.ReplyKeyboardMarkup = inline_kb

    async def _remove_old_telegram_keyboard(message):
        chat = getattr(getattr(message, "chat", None), "id", None)
        if chat is None or chat in _removed_chats:
            return
        try:
            m = await message.reply_text("\u2063", reply_markup=ReplyKeyboardRemove())
            _removed_chats.add(chat)
            try:
                await m.delete()
            except Exception:
                pass
        except Exception:
            pass

    _old_start = B.start
    async def _start_no_reply_keyboard(update, context):
        await _remove_old_telegram_keyboard(update.effective_message)
        return await _old_start(update, context)
    B.start = _start_no_reply_keyboard

    async def _inline_text_callback(update, context):
        q = update.callback_query
        key = str(q.data or "")
        label = _actions.get(key)
        if label is None:
            await q.answer("این گزینه منقضی شده؛ لطفاً منوی جدید را انتخاب کنید.", show_alert=False)
            return
        await q.answer()
        try:
            await _remove_old_telegram_keyboard(q.message)
            # telegram.Message.text is read-only. Bypass TelegramObject.__setattr__
            # only for the duration of routing, then restore the original value.
            original_text = getattr(q.message, "text", None)
            object.__setattr__(q.message, "text", label)
            try:
                await B.router(update, context)
            finally:
                object.__setattr__(q.message, "text", original_text)
        except Exception:
            log.exception("inline Telegram button routing failed: %s", label)
            try:
                await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد.")
            except Exception:
                pass

    _old_build = B.build
    def build_with_inline():
        app = _old_build()
        app.add_handler(CallbackQueryHandler(_inline_text_callback, pattern=r"^ik:"), group=0)
        return app
    B.build = build_with_inline
    log.info("Final Telegram inline-only keyboard bridge installed")
except Exception:
    log.exception("Final Telegram inline keyboard patch failed")

# ---------------- Rubika ----------------
try:
    import rubika_v2 as RB
    _send_lock = threading.Lock()
    _last_send = 0.0

    def _wait_rate(delay=2.0):
        global _last_send
        with _send_lock:
            wait = delay - (time.monotonic() - _last_send)
            if wait > 0:
                time.sleep(wait)
            _last_send = time.monotonic()

    def _rubika_send(chat, text, r=None):
        p = {"chat_id": str(chat), "text": str(text)}
        if r:
            p["inline_keypad"] = {"rows": RB.rows(r)}

        # Do not call editChatKeypad before every message. That extra API call
        # was causing a second request for every user action and contributing to
        # Rubika TOO_REQUESTS. Inline keypad is the only new keyboard we send.
        last_exc = None
        for attempt in range(4):
            try:
                _wait_rate(2.0 if attempt == 0 else min(12.0, 4.0 * attempt))
                z = RB.HTTP.post(f"{RB.BASE}/sendMessage", json=p, timeout=20)
                z.raise_for_status()
                data = z.json()
                if isinstance(data, dict) and data.get("status") == "TOO_REQUESTS":
                    last_exc = RuntimeError("TOO_REQUESTS")
                    # Rubika's rate-limit response is not recoverable by a rapid retry.
                    # Back off substantially so the next real user action can succeed.
                    time.sleep(min(30.0, 8.0 * (attempt + 1)))
                    continue
                return data
            except Exception as exc:
                last_exc = exc
                if attempt >= 3:
                    break
                time.sleep(min(12.0, 3.0 * (attempt + 1)))
        log.error("Rubika send failed after controlled retries: %s", last_exc)
        # Never crash the whole Rubika update worker because a single send hit a
        # provider rate limit. The webhook can acknowledge the update and remain alive.
        return {"status": "RETRY_LATER", "error": str(last_exc or "send failed")}

    def _rubika_call(method, p=None):
        last_exc = None
        for attempt in range(3):
            try:
                _wait_rate(2.0)
                z = RB.HTTP.post(f"{RB.BASE}/{method}", json=p or {}, timeout=20)
                z.raise_for_status()
                d = z.json()
                if isinstance(d, dict) and d.get("status") not in (None, "OK"):
                    if d.get("status") == "TOO_REQUESTS":
                        last_exc = RuntimeError("TOO_REQUESTS")
                        time.sleep(8.0 * (attempt + 1))
                        continue
                    raise RuntimeError(str(d))
                return d.get("data", d) if isinstance(d, dict) else d
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(4.0 * (attempt + 1))
        raise last_exc or RuntimeError(f"Rubika {method} failed")

    RB.send = _rubika_send
    RB.call = _rubika_call
    log.info("Final Rubika inline keypad + controlled rate limiter installed")
except Exception:
    log.exception("Final Rubika stability patch failed")
