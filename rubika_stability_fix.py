"""Rubika client/runtime stability fixes.

Handles first contact from users who do not emit StartedBot, normalizes the
several Rubika sender/chat shapes, and prevents stale per-user state from
blocking language/menu navigation.
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


def install():
    import server
    import rubika_v2 as rb

    if getattr(rb, "_netyar_stability_fix_installed", False):
        return

    # Make identity extraction identical everywhere in the Rubika runtime.
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

        # Some Rubika clients do not emit StartedBot on the first message.
        # Treat /start or a normal greeting as a fresh start for that chat.
        text = rb.text_of(update).strip()
        if text.lower() in {"/start", "start", "شروع", "سلام", "hi", "hello"}:
            rb.restart(str(uid), chat)
            return

        return old_process(update)

    rb.process = process
    rb._netyar_stability_fix_installed = True
    log.warning("Rubika identity/first-contact stability fix installed")
