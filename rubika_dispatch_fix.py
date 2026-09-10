"""Make Rubika webhook updates reach the actual conversation handler.

The provider is successfully POSTing NewMessage updates, but the legacy
process dispatcher can silently ignore the payload shape used by the current
webhook.  The webhook already normalizes the payload, so dispatch directly to
rubika_v2.handle for normal messages/buttons.  File/media states still receive
the original update object.
"""


def install():
    import rubika_v2 as rb
    if getattr(rb, "_netyar_rubika_dispatch_fix", False):
        return

    original_process = rb.process

    def process_fixed(update):
        try:
            uid = rb.user_of(update)
            chat = rb.chat_of(update)
            text = rb.text_of(update)
            if uid and chat:
                return rb.handle(str(uid), str(chat), str(text or ""), update)
        except Exception:
            # Preserve the old dispatcher as a fallback for unusual provider
            # payloads rather than dropping an update silently.
            return original_process(update)
        return original_process(update)

    rb.process = process_fixed
    rb._netyar_rubika_dispatch_fix = True
