"""Deterministic compatibility-layer loader for the production bot.

The application still contains legacy compatibility modules, so their order is
kept explicit here.  Every module exposes an idempotent ``install()`` function.
The final stability layer is loaded last so it protects the public routing and
transport seams after all legacy patches have been applied.
"""

import logging

log = logging.getLogger("netyar.runtime")

# Order matters.  Do not alphabetize this list: several legacy patches extend
# functions installed by earlier patches.
_PATCH_MODULES = (
    "logging_patch",
    "telegram_runtime",
    "hotfix",
    "stability_patch",
    "ui_patch",
    "workflow_patch",
    "partner_code_fix",
    "rubika_core_compat",
    "server_patch",
    "rubika_fix",
    "rubika_runtime_fix",
    "rubika_dispatch_fix",
    "rubika_webhook_fix",
    "integration_hardening",
    "rubika_polling_fallback",
    "rubika_partner_login_fix",
    "telegram_partner_login_fix",
    "telegram_button_fix",
    "business_flow_patch",
    "final_safety_patch",
    "telegram_import_compat",
    "final_ui_flow_patch",
    "ui_consistency_patch",
    "partner_request_patch",
    "iranian_menu_patch",
    "inline_callback_user_fix",
    "button_routing_fix",
    "rubika_button_routing_fix",
    "final_ux_hardening",
    "full_admin_control_patch",
    "admin_control_v2",
    "admin_control_v3",
    "production_final_patch",
    "production_final_hotfix",
    "production_stability",
)


def install():
    """Load the compatibility stack once and return the FastAPI server."""
    import importlib

    server = None
    for module_name in _PATCH_MODULES:
        module = importlib.import_module(module_name)
        if module_name == "server":
            server = module
            continue
        installer = getattr(module, "install", None)
        if installer is None:
            # telegram_runtime is an integration module whose import performs
            # its own setup; every other module in this list is an explicit
            # compatibility patch.
            continue
        installer()
        log.info("runtime patch installed: %s", module_name)

    if server is None:
        import server

    return server
