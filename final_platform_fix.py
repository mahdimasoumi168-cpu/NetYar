"""Final platform hardening: inline-only UI, old-keyboard removal and rate limiting."""
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

    B.kb = inline_kb

    async def _remove_old_telegram_keyboard(message):
        chat = getattr(getattr(message, "chat", None), "id", None)
        if chat is None or chat in _removed_chats:
            return
        try:
            # Telegram keeps reply keyboards until ReplyKeyboardRemove is sent.
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
            original_text = getattr(q.message, "text", None)
            q.message.text = label
            await B.router(update, context)
        except Exception:
            log.exception("inline Telegram button routing failed: %s", label)
            try:
                await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد.")
            except Exception:
                pass
        finally:
            try:
                q.message.text = original_text
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
    _removed_chats = set()

    def _wait_rate():
        global _last_send
        with _send_lock:
            now = time.monotonic()
            delay = 0.65 - (now - _last_send)
            if delay > 0:
                time.sleep(delay)
            _last_send = time.monotonic()

    def _remove_old_rubika_keypad(chat):
        chat = str(chat)
        if chat in _removed_chats:
            return
        try:
            _wait_rate()
            z = RB.HTTP.post(f"{RB.BASE}/editChatKeypad", json={"chat_id": chat, "chat_keypad_type": "Remove"}, timeout=20)
            if z.ok:
                _removed_chats.add(chat)
        except Exception:
            # Removal is best-effort; inline_keypad remains the only keypad sent below.
            pass

    def _rubika_send(chat, text, r=None):
        p = {"chat_id": str(chat), "text": str(text)}
        if r:
            p["inline_keypad"] = {"rows": RB.rows(r)}
        # Remove any legacy bottom ChatKeypad before the first inline-only message.
        _remove_old_rubika_keypad(chat)
        for attempt in range(5):
            try:
                _wait_rate()
                z = RB.HTTP.post(f"{RB.BASE}/sendMessage", json=p, timeout=30)
                z.raise_for_status()
                data = z.json()
                if isinstance(data, dict) and data.get("status") == "TOO_REQUESTS":
                    raise RuntimeError("TOO_REQUESTS")
                return data
            except Exception as exc:
                if attempt >= 4:
                    log.exception("Rubika send failed after retries")
                    raise
                wait = min(8.0, 1.0 * (2 ** attempt))
                if "TOO_REQUESTS" not in str(exc).upper():
                    wait = min(4.0, 0.75 * (attempt + 1))
                log.warning("Rubika send retry %s/4: %s", attempt + 1, exc)
                time.sleep(wait)

    def _rubika_call(method, p=None):
        for attempt in range(5):
            try:
                _wait_rate()
                z = RB.HTTP.post(f"{RB.BASE}/{method}", json=p or {}, timeout=35)
                z.raise_for_status()
                d = z.json()
                if isinstance(d, dict) and d.get("status") not in (None, "OK"):
                    raise RuntimeError(str(d))
                return d.get("data", d) if isinstance(d, dict) else d
            except Exception as exc:
                if attempt >= 4:
                    raise
                wait = min(10.0, 1.5 * (2 ** attempt))
                if "TOO_REQUESTS" not in str(exc).upper():
                    wait = min(5.0, 1.0 + attempt)
                log.warning("Rubika %s retry %s/4: %s", method, attempt + 1, exc)
                time.sleep(wait)

    RB.send = _rubika_send
    RB.call = _rubika_call
    log.info("Final Rubika inline keypad + rate limiter installed")
except Exception:
    log.exception("Final Rubika stability patch failed")
