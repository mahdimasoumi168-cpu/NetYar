"""Rubika stability guard.

Telegram uses python-telegram-bot's native ReplyKeyboardMarkup/InlineKeyboardMarkup.
Do not monkey-patch Telegram keyboard classes or Application.add_handler here:
those compatibility hacks caused normal Telegram reply buttons to be converted
into inline callbacks and made the menu appear to jump between states.
"""
import logging
import threading
import time

log = logging.getLogger("netyar.final_stability")


def install():
    _install_rubika_guard()


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
