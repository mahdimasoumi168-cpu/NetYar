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

    import rubika_core_compat
    rubika_core_compat.install()

    import server

    import server_patch
    server_patch.install()

    import rubika_fix
    rubika_fix.install()

    import rubika_runtime_fix
    rubika_runtime_fix.install()

    import rubika_dispatch_fix
    rubika_dispatch_fix.install()

    import rubika_webhook_fix
    rubika_webhook_fix.install()

    import integration_hardening
    integration_hardening.install()

    import rubika_partner_login_fix
    rubika_partner_login_fix.install()

    import telegram_button_fix
    telegram_button_fix.install()

    import business_flow_patch
    business_flow_patch.install()

    # Must be last: business_flow_patch replaces media(), so this final layer
    # restores the canonical top-up callback format expected by admin_cb().
    import final_safety_patch
    final_safety_patch.install()

    return server
