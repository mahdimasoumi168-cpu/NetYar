"""Final keyboard + Rubika stability patch.

Loaded last by runtime_patches so it wins over legacy UI compatibility layers.
"""
import hashlib
import logging
import sys
import threading
import time

log = logging.getLogger("netyar.final_stability")


def install():
    _install_telegram_inline()
    _install_rubika_guard()


def _install_telegram_inline():
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
        from telegram.ext import Application, CallbackQueryHandler
        import telegram as telegram_pkg

        labels = {}
        removed = set()

        def inline_keyboard(rows):
            out = []
            for row in rows or []:
                buttons = []
                for item in row or []:
                    label = str(getattr(item, "text", item))
                    key = "nyik:" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:16]
                    labels[key] = label
                    buttons.append(InlineKeyboardButton(label, callback_data=key))
                if buttons:
                    out.append(buttons)
            return InlineKeyboardMarkup(out)

        telegram_pkg.ReplyKeyboardMarkup = inline_keyboard

        original_add_handler = getattr(Application.add_handler, "_netyar_original", Application.add_handler)

        class _MessageProxy:
            def __init__(self, original, text):
                self._original = original
                self.text = text

            def __getattr__(self, name):
                return getattr(self._original, name)

        class _UpdateProxy:
            def __init__(self, original, message):
                self._original = original
                self.message = message

            def __getattr__(self, name):
                return getattr(self._original, name)

        async def callback(update, context):
            q = update.callback_query
            key = q.data or ""
            label = labels.get(key)
            if not label or not q.message:
                await q.answer()
                return

            await q.answer()

            try:
                chat_id = q.message.chat_id
                if chat_id not in removed:
                    await q.message.reply_text("\u200b", reply_markup=ReplyKeyboardRemove())
                    removed.add(chat_id)
            except Exception:
                pass

            bot = sys.modules.get("bot")
            if bot is None or not hasattr(bot, "router"):
                return

            # python-telegram-bot Message objects are immutable. Never assign
            # to q.message.text. Pass a lightweight update/message proxy to the
            # existing router instead.
            proxy_message = _MessageProxy(q.message, label)
            proxy_update = _UpdateProxy(update, proxy_message)
            await bot.router(proxy_update, context)

        def add_handler(self, handler, group=0):
            result = original_add_handler(self, handler, group)
            if not getattr(self, "_netyar_inline_handler_added", False):
                self._netyar_inline_handler_added = True
                original_add_handler(self, CallbackQueryHandler(callback, pattern=r"^nyik:"), 99)
            return result

        add_handler._netyar_original = original_add_handler
        Application.add_handler = add_handler

        bot = sys.modules.get("bot")
        if bot is not None:
            bot.kb = inline_keyboard

        log.info("final Telegram inline keyboard patch installed")
    except Exception:
        log.exception("final Telegram inline keyboard patch failed")


def _install_rubika_guard():
    try:
        import requests

        lock = threading.Lock()
        state = {"last": 0.0}
        removed_chats = set()
        original = getattr(requests.Session.post, "_netyar_original", requests.Session.post)

        def post(self, url, *args, **kwargs):
            if not isinstance(url, str) or "botapi.rubika.ir/v3/" not in url:
                return original(self, url, *args, **kwargs)

            payload = kwargs.get("json")
            method = url.rsplit("/", 1)[-1]
            chat_id = payload.get("chat_id") if isinstance(payload, dict) else None

            with lock:
                wait = 0.95 - (time.monotonic() - state["last"])
                if wait > 0:
                    time.sleep(wait)

                if method in ("sendMessage", "sendFile") and isinstance(payload, dict):
                    keypad = payload.pop("chat_keypad", None)
                    payload.pop("chat_keypad_type", None)
                    if keypad and "inline_keypad" not in payload:
                        payload["inline_keypad"] = keypad

                response = None
                for attempt in range(5):
                    response = original(self, url, *args, **kwargs)
                    state["last"] = time.monotonic()
                    try:
                        body = response.json()
                    except Exception:
                        body = {}
                    status = body.get("status") if isinstance(body, dict) else None
                    if status != "TOO_REQUESTS":
                        break
                    if attempt < 4:
                        time.sleep(min(10.0, 1.5 * (2 ** attempt)))

                if method == "sendMessage" and chat_id and str(chat_id) not in removed_chats and response is not None:
                    try:
                        time.sleep(0.95)
                        remove_url = url.rsplit("/", 1)[0] + "/editChatKeypad"
                        rr = original(
                            self,
                            remove_url,
                            json={"chat_id": str(chat_id), "chat_keypad_type": "Remove"},
                            timeout=20,
                        )
                        state["last"] = time.monotonic()
                        try:
                            rb = rr.json()
                            if not (isinstance(rb, dict) and rb.get("status") == "TOO_REQUESTS"):
                                removed_chats.add(str(chat_id))
                        except Exception:
                            removed_chats.add(str(chat_id))
                    except Exception:
                        pass

                return response

        post._netyar_original = original
        requests.Session.post = post
        log.info("final Rubika rate-limit/inline-keypad patch installed")
    except Exception:
        log.exception("final Rubika stability patch failed")
