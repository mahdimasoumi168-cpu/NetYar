"""Final Rubika compatibility/stability layer.

Keeps Rubika's native keypad usable by preserving the menu-defined button ids
and normalizing incoming native button payloads. Telegram keeps its inline
keyboard policy separately.
"""
import json
import logging

log = logging.getLogger("netyar.rubika.final")


def install():
    import rubika_v2 as R
    if getattr(R, "_netyar_rubika_final_stability", False):
        return

    def native_rows(rows):
        out = []
        for row in rows or []:
            buttons = []
            for i, item in enumerate(row or []):
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    button_id, label = str(item[0]), str(item[1])
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
        m = update.get("message") or update.get("new_message") or update
        if not isinstance(m, dict):
            return ""
        aux = m.get("aux_data")
        if isinstance(aux, str):
            try:
                aux = json.loads(aux)
            except Exception:
                aux = None
        if isinstance(aux, dict):
            # Native Rubika keypad returns the menu-defined button id here.
            button_id = aux.get("button_id")
            if button_id is not None and str(button_id).strip():
                return str(button_id).strip()
            for key in ("button_text", "text"):
                if aux.get(key):
                    return str(aux[key]).strip()
        for key in ("button_id", "button_text", "text"):
            if m.get(key):
                return str(m[key]).strip()
        return ""

    R.rows = native_rows
    R.text_of = payload_text
    R._netyar_rubika_final_stability = True
    log.info("final Rubika native keypad routing installed")
