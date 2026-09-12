"""Last-mile Rubika navigation guard.

Keeps duplicate-event protection while making main-menu rows deterministic.
Cancel is reserved for data-entry flows; the main menu always exposes restart.
"""
import hashlib
import logging
log = logging.getLogger("netyar.rubika_navigation")


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
        if not getattr(rb, "_nav_main_fixed", False):
            old_rows = getattr(rb, "main_rows", None)
            if old_rows:
                def main_rows(uid):
                    source = old_rows(uid) or []
                    rows = []
                    for row in source:
                        out = []
                        for i, item in enumerate(row or []):
                            bid = str(item[0]) if isinstance(item, (tuple, list)) and len(item) >= 2 else str(i)
                            label = str(item[1]) if isinstance(item, (tuple, list)) and len(item) >= 2 else str(item)
                            if label in {"❌ Cancel", "❌ إلغاء", "❌ انصراف", "❌ لغو", "❌ انصراف"}:
                                label = "🔄 شروع مجدد" if rb.STATE.get(str(uid), {}).get("lang", "fa") == "fa" else ("🔄 Restart" if rb.STATE.get(str(uid), {}).get("lang") == "en" else "🔄 بدء من جديد")
                            out.append((bid, label))
                        if out:
                            rows.append(out)
                    return rows
                rb.main_rows = main_rows
                rb._nav_main_fixed = True

        if not getattr(rb, "_nav_handle_fixed", False):
            old_handle = rb.handle
            def handle(uid, chat, x, u):
                text = str(x or "").strip()
                if text in {"🔄 شروع مجدد", "🔄 Restart", "🔄 بدء من جديد"}:
                    lang = rb.STATE.get(str(uid), {}).get("lang", "fa")
                    rb.STATE[str(uid)] = {"lang": lang, "step": "language"}
                    labels = {
                        "fa": [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]],
                        "en": [[("1", "🇮🇷 Persian"), ("2", "🇬🇧 English"), ("3", "🇸🇦 Arabic")]],
                        "ar": [[("1", "🇮🇷 الفارسية"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]],
                    }
                    return rb.send(chat, rb.TEXT.get(lang, rb.TEXT["fa"])["lang"], labels.get(lang, labels["fa"]))
                return old_handle(uid, chat, x, u)
            rb.handle = handle
            rb._nav_handle_fixed = True
    except Exception:
        log.exception("Rubika navigation patch failed")
    log.info("Rubika navigation/dedup guard installed")
