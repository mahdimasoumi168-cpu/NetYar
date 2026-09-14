"""Final UI rebind.

Some legacy service layers replace B.main with a reply-keyboard implementation.
The canonical UI layer uses tokenized inline callbacks, so rebind B.main after
all feature installers have completed without registering duplicate handlers.
"""

def install(app, B):
    import telegram_ui_policy_v2 as UI

    def main(uid):
        return UI.inline(UI._main_rows(B, uid), B, uid)

    B.main = main
    B.cancel_kb = lambda lang="fa": UI.inline([[UI.CANCEL]], B, UI._uid() or 0)
    return True
