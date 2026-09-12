"""Final Rubika navigation/UI stability layer.

Button labels stay clean (no artificial color-prefix icons). Native Rubika
keypads provide the actual button UI; this layer only normalizes routing.
Cancel returns to the menu of the current mode, while restart returns to the
language/citizenship start flow without leaving stale state behind.
"""
import hashlib
import logging
log = logging.getLogger("netyar.rubika_navigation")


def _clean_label(label):
    s = str(label or "").strip()
    # Remove only the artificial visual prefix introduced by older UI patches.
    for prefix in ("🔵 ", "🟦 ", "🟩 ", "🟨 "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s


def _clean_rows(rows):
    out = []
    for row in rows or []:
        rr = []
        for i, item in enumerate(row or []):
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                rr.append((str(item[0]), _clean_label(item[1])))
            elif isinstance(item, dict):
                rr.append({**item, "button_text": _clean_label(item.get("button_text") or item.get("text") or item.get("label"))})
            else:
                rr.append((str(i), _clean_label(item)))
        if rr:
            out.append(rr)
    return out


def install():
    try:
        import server
        def stable_key(update):
            u = update.get("update") if isinstance(update, dict) and isinstance(update.get("update"), dict) else update
            if not isinstance(u, dict):
                return repr(update)
            m = u.get("message") or u.get("new_message") or u
            if not isinstance(m, dict):
                m = {}
            typ = str(u.get("type", ""))
            chat = str(u.get("chat_id") or m.get("chat_id") or m.get("chat_key") or "")
            sender = m.get("sender") or {}
            user = str(sender.get("user_id") or m.get("sender_id") or m.get("user_id") or chat)
            mid = str(m.get("message_id") or u.get("message_id") or "")
            text = str(m.get("text") or m.get("button_text") or "")
            raw = f"{typ}|{chat}|{user}|{mid or text}"
            return hashlib.sha256(raw.encode()).hexdigest()
        server._rb_key = stable_key
    except Exception:
        log.exception("Rubika server navigation guard failed")

    try:
        import rubika_v2 as rb
        # Preserve the existing functional menu and clean its labels instead of
        # replacing its button IDs. This prevents routing regressions.
        old_rows = getattr(rb, "main_rows", None)
        if old_rows and not getattr(rb, "_nav_main_fixed", False):
            def main_rows(uid):
                return _clean_rows(old_rows(uid) or [])
            rb.main_rows = main_rows
            rb._nav_main_fixed = True

        # Every send boundary receives cleaned labels. IDs are never changed.
        old_send = rb.send
        if not getattr(rb, "_nav_send_fixed", False):
            def send_clean(chat, text, r=None):
                return old_send(chat, text, _clean_rows(r) if r else r)
            rb.send = send_clean
            rb._nav_send_fixed = True

        if not getattr(rb, "_nav_handle_fixed", False):
            old_handle = rb.handle
            def handle(uid, chat, x, u):
                text = _clean_label(x)
                state = rb.STATE.setdefault(str(uid), {})
                lang = state.get("lang", "fa")
                # Restart: clear only transient workflow state; preserve language
                # and the user's citizenship choice where available.
                if text in {"🔄 شروع مجدد", "🔄 Restart", "🔄 بدء من جديد", "شروع مجدد", "Restart"}:
                    citizenship = state.get("citizenship") or state.get("status")
                    rb.STATE[str(uid)] = {"lang": lang}
                    if citizenship:
                        rb.STATE[str(uid)]["citizenship"] = citizenship
                        rb.STATE[str(uid)]["status"] = citizenship
                    rb.STATE[str(uid)]["step"] = "citizenship"
                    return old_handle(uid, chat, "", u)

                # Cancel must not turn the current menu into an unrelated menu.
                if text in {"❌ انصراف", "انصراف", "Cancel", "cancel", "إلغاء", "لغو"}:
                    step = state.get("step", "")
                    if step in {"partner_ticket", "partner_ticket_chat", "ticket_admin_reply"}:
                        state["step"] = "partner"
                        return rb.send(chat, "❌ عملیات لغو شد.", _clean_rows(rb.partner_rows()))
                    if step in {"admin_ticket_chat", "admin_ticket_reply"}:
                        state["step"] = "admin"
                        return rb.send(chat, "❌ عملیات لغو شد.", _clean_rows(rb.admin_rows()))
                    if step.startswith("admin_"):
                        state["step"] = "admin"
                        return rb.send(chat, "❌ عملیات لغو شد.", _clean_rows(rb.admin_rows()))
                    # For customer data-entry flows, preserve citizenship and
                    # return to the matching Iranian/foreign main menu.
                    if state.get("status") == "iranian":
                        state["step"] = "iranian"
                        return rb.send(chat, "❌ عملیات لغو شد.", _clean_rows(rb.iran_rows(uid)))
                    state["step"] = "main"
                    return rb.send(chat, "❌ عملیات لغو شد.", _clean_rows(rb.main_rows(uid)))

                return old_handle(uid, chat, text, u)
            rb.handle = handle
            rb._nav_handle_fixed = True
    except Exception:
        log.exception("Rubika navigation patch failed")
    log.info("Rubika navigation/UI guard installed")
