"""Final Rubika button routing fix.

Rubika's keypad was assigning button ids from 0/1 for every row. Because the
counter restarted on each row, several different buttons shared the same id.
Some NewMessage payloads return that id instead of button_text, so unrelated
buttons could all enter the same branch. Use the visible label as the stable
button id and prefer button_text when Rubika supplies it.
"""
import json
import logging

log = logging.getLogger("netyar.rubika_button_routing_fix")


def install():
    import rubika_v2 as rb
    if getattr(rb, "_rubika_button_routing_fix_installed", False):
        return

    def stable_rows(r):
        out = []
        for row in r or []:
            buttons = []
            for item in row or []:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    label = str(item[1])
                else:
                    label = str(item)
                buttons.append({
                    "id": label,
                    "type": "Simple",
                    "button_text": label,
                })
            if buttons:
                out.append({"buttons": buttons})
        return out

    def stable_text_of(u):
        m = u.get("message") or u.get("new_message") or u
        if not isinstance(m, dict):
            return ""
        # Prefer the actual visible label over an opaque provider id.
        for k in ("text", "button_text"):
            if m.get(k):
                return str(m[k]).strip()
        a = m.get("aux_data")
        if isinstance(a, dict):
            for k in ("button_text", "text", "button_id"):
                if a.get(k):
                    return str(a[k]).strip()
        if isinstance(a, str):
            try:
                a = json.loads(a)
                if isinstance(a, dict):
                    for k in ("button_text", "text", "button_id"):
                        if a.get(k):
                            return str(a[k]).strip()
            except Exception:
                pass
        return ""

    rb.rows = stable_rows
    rb.text_of = stable_text_of
    rb._rubika_button_routing_fix_installed = True
    log.info("stable Rubika button ids installed")
