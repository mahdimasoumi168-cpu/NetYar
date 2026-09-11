"""Single compatibility layer for the current production runtime."""


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

    import final_safety_patch
    final_safety_patch.install()

    import telegram_import_compat
    telegram_import_compat.install()

    import final_ui_flow_patch
    final_ui_flow_patch.install()

    import ui_consistency_patch
    ui_consistency_patch.install()

    import partner_request_patch
    partner_request_patch.install()

    import iranian_menu_patch
    iranian_menu_patch.install()

    # Must be last: fixes the stale process-global owner check used by inline
    # Telegram callbacks and removes «این دکمه برای کاربر دیگری است».
    import inline_callback_user_fix
    inline_callback_user_fix.install()

    return server
