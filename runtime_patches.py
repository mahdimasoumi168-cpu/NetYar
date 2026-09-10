"""Single compatibility layer for the current production runtime.

The bot still contains a few historical provider-specific fixes. Keep their
load order in one place so entrypoint.py remains small and deterministic while
those fixes are gradually folded into the main platform modules.
"""


def install():
    import logging_patch
    logging_patch.install()

    import telegram_runtime  # noqa: F401

    import hotfix
    hotfix.install()

    import stability_patch
    stability_patch.install()

    import ui_patch
    ui_patch.install()

    import workflow_patch
    workflow_patch.install()

    import partner_code_fix
    partner_code_fix.install()

    import server

    import server_patch
    server_patch.install()

    return server
