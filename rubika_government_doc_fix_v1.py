"""Isolated Rubika fix for Government 'document type' keypad routing.

Only patches Rubika's numeric-button normalizer. Telegram is untouched.
"""


def install(rb=None):
    if rb is None:
        import rubika_v2 as rb
    if getattr(rb, "_netyar_rubika_gov_doc_fix_v1", False):
        return

    try:
        import server
        previous = getattr(server, "_normalize_rubika_button", None)

        def normalize(update, R=rb):
            try:
                raw = str(server._rubika_text(update) or "").strip()
                if raw not in {"0", "1", "2", "3", "4"}:
                    return previous(update, R) if callable(previous) else update

                uid = str(server._rubika_user(update))
                step = str(R.STATE.get(uid, {}).get("step") or "")

                # The government flow displays four document buttons with
                # numeric Rubika ids. Convert the click to the exact Persian
                # label expected by the legacy handler before dispatch.
                if step in {"gov_doc", "partner_gov_doc", "government_doc"}:
                    labels = {
                        "1": "کارت آمایش",
                        "2": "کارت موقت",
                        "3": "پاسپورت",
                        "4": "دفترچه اقامت",
                    }
                    if raw == "0":
                        label = R.CANCEL
                    else:
                        label = labels.get(raw)
                    if label:
                        m = server._rubika_message(update)
                        if isinstance(m, dict):
                            m["text"] = label
                        return update
            except Exception:
                # Never break the Rubika receiver because of the compatibility
                # layer; fall back to the existing normalizer.
                pass
            return previous(update, R) if callable(previous) else update

        server._normalize_rubika_button = normalize
    except Exception:
        pass

    rb._netyar_rubika_gov_doc_fix_v1 = True
