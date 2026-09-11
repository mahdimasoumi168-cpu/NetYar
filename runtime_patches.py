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

    # Compatibility shim must run before final_ui_flow_patch because that
    # patch imports CallbackQueryHandler from the top-level telegram module.
    import telegram_import_compat
    telegram_import_compat.install()

    # Final layer: Telegram inline menus and exact government identifier/data flow.
    import final_ui_flow_patch
    final_ui_flow_patch.install()

    # Last UI layer: fixed keyboard order, language selection, support contact,
    # partner-panel label and two-admin compatibility.
    import ui_consistency_patch
    ui_consistency_patch.install()

    # Partner request receipt/ticket actions and Rubika -> Telegram admin mirror.
    import partner_request_patch
    partner_request_patch.install()

    # Final Iranian-user menu and colored management label.
    import iranian_menu_patch
    iranian_menu_patch.install()

    return server
