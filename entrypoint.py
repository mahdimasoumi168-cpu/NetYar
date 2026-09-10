# Import the Telegram runtime first so all UI/router patches wrap the final handlers.
import telegram_runtime
import hotfix
hotfix.install()
import stability_patch
stability_patch.install()
import ui_patch
ui_patch.install()

import server
import server_patch
server_patch.install()

if __name__ == "__main__":
    server.main()
