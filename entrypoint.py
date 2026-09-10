# Import all runtime/reliability layers before starting the server so every handler uses the final behavior.
import logging_patch
logging_patch.install()
import telegram_runtime
import hotfix
hotfix.install()
import stability_patch
stability_patch.install()
import ui_patch
ui_patch.install()
import workflow_patch
workflow_patch.install()

import server
import server_patch
server_patch.install()

if __name__ == "__main__":
    server.main()
