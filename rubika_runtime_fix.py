"""Runtime fixes for Rubika keypad routing.

Rubika sends the button id back in aux_data.button_id. The old server helper
replaced explicit tuple/list ids with the column index, producing duplicate
0/1 ids on every row. Keep the IDs supplied by the menu definitions.
"""

def install():
    import server

    if getattr(server, "_netyar_rubika_keypad_fix", False):
        return

    def safe_rows(rows):
        out = []
        for row in rows or []:
            buttons = []
            for i, item in enumerate(row or []):
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    button_id, label = str(item[0]), str(item[1])
                else:
                    button_id, label = str(i), str(item)
                buttons.append({
                    "id": button_id,
                    "type": "Simple",
                    "button_text": label,
                })
            if buttons:
                out.append({"buttons": buttons})
        return out

    server._safe_rubika_rows = safe_rows
    server._netyar_rubika_keypad_fix = True
