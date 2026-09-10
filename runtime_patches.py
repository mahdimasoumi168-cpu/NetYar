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

    # Bridge Rubika's historical DB method names to the unified core database.
    import rubika_core_compat
    rubika_core_compat.install()

    import server

    import server_patch
    server_patch.install()

    # Rubika keypad compatibility: normalize legacy flat [id, label] rows
    # before rubika_v2.send serializes them, and preserve explicit button IDs.
    import rubika_fix
    rubika_fix.install()

    import rubika_runtime_fix
    rubika_runtime_fix.install()

    # Rubika's webhook is receiving NewMessage events, but the legacy process
    # dispatcher can silently ignore the current payload shape. Route the
    # normalized update directly to rubika_v2.handle.
    import rubika_dispatch_fix
    rubika_dispatch_fix.install()

    # Register a conventional receiveUpdate-compatible endpoint and rewrite
    # the provider registration call to use it.
    import rubika_webhook_fix
    rubika_webhook_fix.install()

    # Retry startup webhook registration and answer provider HEAD probes fast.
    import integration_hardening
    integration_hardening.install()

    # Make Rubika partner login tolerant of Persian/Arabic phone digits and
    # legacy phone formatting, without changing the existing state machine.
    import rubika_partner_login_fix
    rubika_partner_login_fix.install()

    # Must be loaded after all historical UI patches so every ReplyKeyboard
    # created by them passes through the same plain-text normalizer.
    import telegram_button_fix
    telegram_button_fix.install()

    return server
