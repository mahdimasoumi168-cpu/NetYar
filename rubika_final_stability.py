"""Final Rubika compatibility/stability layer.

Rubika uses its native keypad. Visible labels stay readable while incoming
button events resolve to the exact menu-defined ids expected by the existing
handler. This layer is intentionally loaded last.
"""
import json
import logging

log = logging.getLogger("netyar.rubika.final")


def _message(update):
    if not isinstance(update, dict):
        return {}
    return update.get("message") or update.get("new_message") or update


def _aux(update):
    m = _message(update)
    value = m.get("aux_data") if isinstance(m, dict) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = None
    return value if isinstance(value, dict) else {}


def _label_to_id(rb, uid, value):
    value = str(value or "").strip()
    if not value:
        return value
    # Search the actual current menus instead of maintaining a second list of
    # labels. This keeps Rubika aligned with future menu changes.
    menus = []
    for name in ("main_rows", "partner_rows", "admin_rows"):
        fn = getattr(rb, name, None)
        if not callable(fn):
            continue
        try:
            menus.append(fn(uid) if name == "main_rows" else fn())
        except Exception:
            continue
    for menu in menus:
        for row in menu or []:
            for item in row or []:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    if str(item[1]).strip() == value:
                        return str(item[0]).strip()
                elif isinstance(item, dict):
                    label = item.get("button_text") or item.get("text") or item.get("label")
                    bid = item.get("id") or item.get("button_id")
                    if label is not None and str(label).strip() == value and bid is not None:
                        return str(bid).strip()
    return value


def _normalise_row(row):
    """Accept both [(id,label), ...] and [id,label] legacy rows."""
    if isinstance(row, (tuple, list)) and len(row) == 2 and not isinstance(row[0], (tuple, list, dict)):
        return [(str(row[0]), str(row[1]))]
    return list(row or [])


def install():
    import rubika_v2 as R
    if getattr(R, "_netyar_rubika_final_stability", False):
        return

    def native_rows(rows):
        out = []
        for row in rows or []:
            buttons = []
            for i, item in enumerate(_normalise_row(row)):
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    button_id, label = str(item[0]), str(item[1])
                elif isinstance(item, dict):
                    button_id = str(item.get("id") or item.get("button_id") or i)
                    label = str(item.get("button_text") or item.get("text") or item.get("label") or "")
                else:
                    button_id, label = str(i + 1), str(item)
                buttons.append({
                    "id": button_id,
                    "type": "Simple",
                    "button_text": label,
                })
            if buttons:
                out.append({"buttons": buttons})
        return out

    def payload_text(update):
        m = _message(update)
        if not isinstance(m, dict):
            return ""
        aux = _aux(update)
        # Always prefer the provider's explicit button id.
        for source in (aux, m, update):
            if isinstance(source, dict):
                button_id = source.get("button_id") or source.get("id")
                if button_id not in (None, ""):
                    return str(button_id).strip()
        # Fall back to visible text only when no id exists.
        for source in (aux, m, update):
            if isinstance(source, dict):
                for key in ("button_text", "text"):
                    value = source.get(key)
                    if value not in (None, ""):
                        return _label_to_id(R, R.user_of(update), str(value).strip())
        return ""

    R.rows = native_rows
    R.text_of = payload_text
    R._netyar_rubika_final_stability = True
    log.info("final Rubika native keypad routing installed")
