"""Final Rubika input guard.

Rubika can deliver a native keypad press as button_id or as the visible
button_text. The legacy handlers use ids in several states. This final layer
normalizes only known menu labels to their ids and leaves free-form user input
untouched.
"""
import logging

log = logging.getLogger("netyar.rubika.button_guard")


def _label_to_id(rb, uid, value):
    value = str(value or "").strip()
    if not value:
        return value
    if value in {"❌ انصراف", "انصراف", "لغو", "Cancel", "cancel", "إلغاء"}:
        return "❌ انصراف"
    if value in {"🔄 شروع مجدد", "شروع مجدد", "/start", "start"}:
        return "99"
    aliases = {
        "👥 پنل همکاران": "1",
        "🔵 👥 پنل همکاران": "1",
        "پنل همکاران": "1",
        "🎫 پیگیری": "2",
        "پیگیری": "2",
    }
    if value in aliases:
        step = rb.STATE.get(str(uid), {}).get("step", "")
        if step == "iranian":
            return "1" if "پنل" in value else "2"
        return aliases[value]
    for name in ("main_rows", "partner_rows", "admin_rows"):
        fn = getattr(rb, name, None)
        if not callable(fn):
            continue
        try:
            menu = fn(uid) if name == "main_rows" else fn()
        except Exception:
            continue
        for row in menu or []:
            for item in row or []:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    if str(item[1]).strip() == value:
                        return str(item[0]).strip()
    return value


def install():
    import rubika_v2 as rb
    if getattr(rb, "_netyar_button_guard_installed", False):
        return
    original = rb.handle

    def handle(uid, chat, x, update):
        normalized = _label_to_id(rb, uid, x)
        return original(uid, chat, normalized, update)

    rb.handle = handle
    rb._netyar_button_guard_installed = True
    log.info("final Rubika button input guard installed")
