"""Runtime compatibility fixes for Rubika keyboards.

Some call sites pass a Rubika row as [button_id, label] while the legacy
rows() helper expects [(button_id, label)].  Without normalization, the ID and
label become two separate buttons.  Normalize that form before rubika_v2.send
builds the keypad.  This is deliberately isolated so the existing workflow is
not rewritten.
"""

def _normalize_rows(rows):
    out = []
    for row in rows or []:
        if isinstance(row, (list, tuple)) and len(row) == 2:
            a, b = row
            # A flat [id, label] row is one button, not two buttons.
            if not isinstance(a, (list, tuple, dict)) and not isinstance(b, (list, tuple, dict)):
                out.append([(str(a), str(b))])
                continue
        out.append(row)
    return out


def install():
    import rubika_v2 as rb
    if getattr(rb, "_netyar_rubika_fix", False):
        return
    original_send = rb.send

    def send_fixed(chat, text, r=None):
        return original_send(chat, text, _normalize_rows(r))

    rb.send = send_fixed
    rb._netyar_rubika_fix = True
