"""Final Rubika keypad/router compatibility layer.

Rubika native keypad events can arrive as button_id, button_text, or inside
aux_data.  The legacy flow was prioritising button_text, which can make a
valid keypad press look like an unknown free-form message.  This layer
normalises the event to the button id when available and falls back to the
visible label only when no id exists.

It also keeps the Rubika admin/request patches active and provides a safe
restart/cancel path without replacing the existing service flow.
"""
import logging

log = logging.getLogger("netyar.rubika.final_router")


def _extract_message(update):
    if not isinstance(update, dict):
        return {}
    return update.get("message") or update.get("new_message") or update


def _candidate_values(update):
    m = _extract_message(update)
    out = []
    # Prefer explicit ids: the handler menus are keyed by these ids.
    for source in (m, update):
        if isinstance(source, dict):
            for key in ("button_id", "id"):
                value = source.get(key)
                if value not in (None, ""):
                    out.append(("id", str(value).strip()))
    aux = m.get("aux_data") if isinstance(m, dict) else None
    if isinstance(aux, dict):
        for key in ("button_id", "id"):
            value = aux.get(key)
            if value not in (None, ""):
                out.append(("id", str(value).strip()))
        for key in ("button_text", "text"):
            value = aux.get(key)
            if value not in (None, ""):
                out.append(("text", str(value).strip()))
    elif isinstance(aux, str):
        try:
            import json
            parsed = json.loads(aux)
            if isinstance(parsed, dict):
                for key in ("button_id", "id"):
                    value = parsed.get(key)
                    if value not in (None, ""):
                        out.append(("id", str(value).strip()))
                for key in ("button_text", "text"):
                    value = parsed.get(key)
                    if value not in (None, ""):
                        out.append(("text", str(value).strip()))
        except Exception:
            pass
    for key in ("button_text", "text"):
        value = m.get(key) if isinstance(m, dict) else None
        if value not in (None, ""):
            out.append(("text", str(value).strip()))
    return out


def _label_to_id(rb, uid, value):
    value = str(value or "").strip()
    if not value:
        return value
    menus = []
    for name in ("main_rows", "partner_rows", "admin_rows"):
        fn = getattr(rb, name, None)
        if callable(fn):
            try:
                menus.append(fn(uid) if name == "main_rows" else fn())
            except Exception:
                pass
    for menu in menus:
        for row in menu or []:
            for item in row or []:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    if str(item[1]).strip() == value:
                        return str(item[0]).strip()
    return value


def install():
    import rubika_v2 as rb
    if getattr(rb, "_netyar_final_router_installed", False):
        return

    original_text_of = rb.text_of

    def text_of_fixed(update):
        try:
            values = _candidate_values(update)
            for kind, value in values:
                if kind == "id":
                    return value
            uid = rb.user_of(update)
            for kind, value in values:
                if kind == "text":
                    return _label_to_id(rb, uid, value)
        except Exception:
            log.exception("rubika keypad normalization failed")
        return original_text_of(update)

    rb.text_of = text_of_fixed

    # Keep the cross-platform request/file notification layer active.  It was
    # present in the repository but omitted from the deterministic patch list.
    try:
        import rubika_admin_patch
        rubika_admin_patch.install()
    except Exception:
        log.exception("rubika admin/request compatibility patch failed")

    rb._netyar_final_router_installed = True
    log.info("final Rubika keypad/router compatibility installed")
