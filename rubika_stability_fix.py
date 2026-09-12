"""Rubika client/runtime stability fixes.

Keeps Rubika identity extraction consistent and makes the first language step
independent of client-specific button payload shapes. This prevents one client
from getting stuck on the language screen while another client works.
"""
import logging

log = logging.getLogger("netyar.rubika.stability")


def _inner(u):
    if isinstance(u, dict) and isinstance(u.get("update"), dict):
        return u["update"]
    return u if isinstance(u, dict) else {}


def _message(u):
    x = _inner(u)
    m = x.get("message") or x.get("new_message") or x.get("inline_message") or x
    return m if isinstance(m, dict) else {}


def _chat(u):
    x = _inner(u)
    m = _message(x)
    for source in (x, m):
        if not isinstance(source, dict):
            continue
        for key in ("chat_id", "chat_key", "object_guid"):
            value = source.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""


def _user(u):
    x = _inner(u)
    m = _message(x)
    candidates = []
    for source in (m, x):
        if isinstance(source, dict):
            sender = source.get("sender")
            if isinstance(sender, dict):
                candidates.extend([sender.get("user_id"), sender.get("user_guid"), sender.get("id")])
            candidates.extend([source.get("sender_id"), source.get("user_id"), source.get("user_guid")])
    candidates.append(_chat(x))
    for value in candidates:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _button_value(update):
    """Return a Rubika button's logical id/text across client payload variants."""
    m = _message(update)
    aux = m.get("aux_data")
    if isinstance(aux, str):
        try:
            import json
            aux = json.loads(aux)
        except Exception:
            aux = None
    if isinstance(aux, dict):
        for key in ("button_id", "button_text", "text"):
            value = aux.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    for key in ("button_id", "button_text", "text"):
        value = m.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _language_selection(rb, uid, chat, update):
    """Handle language selection before any legacy/compatibility router."""
    raw = _button_value(update)
    languages = {
        "1": "fa", "🇮🇷 فارسی": "fa", "فارسی": "fa",
        "2": "en", "🇬🇧 English": "en", "English": "en",
        "3": "ar", "🇸🇦 العربية": "ar", "العربية": "ar",
    }
    selected = languages.get(raw)
    if not selected:
        return False

    st = rb.STATE.setdefault(str(uid), {})
    # Only consume these values while the user is actually on language step.
    if st.get("step") != "language":
        return False

    st["lang"] = selected
    st["step"] = "citizenship"
    if selected == "fa":
        rows = [[("1", "🪪 اتباع هستم"), ("2", "🇮🇷 ایرانی هستم")]]
    elif selected == "en":
        rows = [[("1", "🪪 Foreign national"), ("2", "🇮🇷 Iranian")]]
    else:
        rows = [[("1", "🪪 أجنبي"), ("2", "🇮🇷 إيراني")]]
    rb.send(chat, rb.T(uid, "cit"), rows)
    log.info("Rubika language selected: user=%s chat=%s lang=%s", uid, chat, selected)
    return True


def install():
    import server
    import rubika_v2 as rb

    if getattr(rb, "_netyar_stability_fix_installed", False):
        return

    rb.chat_of = _chat
    rb.user_of = _user
    server._rubika_chat = _chat
    server._rubika_user = _user

    old_process = rb.process

    def process(update):
        uid = _user(update)
        chat = _chat(update)
        if not uid or not chat:
            log.warning("Rubika update ignored: missing user/chat identity")
            return

        st = rb.STATE.setdefault(str(uid), {})
        if not st.get("lang"):
            st["lang"] = "fa"
        if not st.get("step"):
            st["step"] = "language"

        text = rb.text_of(update).strip()
        if text.lower() in {"/start", "start", "شروع", "سلام", "hi", "hello"}:
            rb.restart(str(uid), chat)
            return

        # Handle language selection before the legacy router. Rubika clients
        # differ in whether they send button_id, button_text or plain text.
        if _language_selection(rb, str(uid), chat, update):
            return

        return old_process(update)

    rb.process = process
    rb._netyar_stability_fix_installed = True
    log.info("Rubika identity/first-contact/language stability fix installed")
