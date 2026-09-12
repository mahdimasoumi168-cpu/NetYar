"""Deterministic compatibility-layer loader for the production bot.

Legacy patch files are still loaded in their historical order for backwards
compatibility. The final inline-only Telegram patch is intentionally excluded:
it replaced normal reply keyboards and was the source of inconsistent Telegram
UI/routing. A single production hotfix is loaded last for deterministic fixes.
"""
import importlib
import logging

log = logging.getLogger("netyar.runtime")

_PATCH_MODULES = (
    "logging_patch", "telegram_runtime", "hotfix", "stability_patch", "ui_patch",
    "workflow_patch", "partner_code_fix", "rubika_core_compat", "server", "server_patch",
    "rubika_fix", "rubika_runtime_fix", "rubika_dispatch_fix", "rubika_webhook_fix",
    "integration_hardening", "rubika_polling_fallback", "rubika_partner_login_fix",
    "telegram_partner_login_fix", "telegram_button_fix", "business_flow_patch",
    "final_safety_patch", "telegram_import_compat", "final_ui_flow_patch",
    "ui_consistency_patch", "partner_request_patch", "iranian_menu_patch",
    "inline_callback_user_fix", "button_routing_fix", "rubika_button_routing_fix",
    "final_ux_hardening", "full_admin_control_patch", "admin_control_v2", "admin_control_v3",
    "production_final_patch", "production_final_hotfix", "production_stability",
    "final_requirements_patch", "production_final_v2", "rubika_final_router",
    "rubika_admin_full", "rubika_final_stability", "rubika_final_stability_patch",
    "rubika_button_guard", "admin_control_v4", "admin_control_v5", "rubika_admin_control_v5",
    "admin_full_v6", "keyboard_rubika_stability", "production_hotfix_v3",
)


def install():
    server = None
    for module_name in _PATCH_MODULES:
        try:
            module = importlib.import_module(module_name)
            if module_name == "server":
                server = module
                continue
            installer = getattr(module, "install", None)
            if installer is not None:
                installer()
                log.info("runtime patch installed: %s", module_name)
        except Exception:
            # One optional compatibility patch must never prevent the server
            # from starting. The real integration modules are still allowed
            # to fail loudly through their own startup checks/logging.
            log.exception("runtime patch failed: %s", module_name)
    if server is None:
        server = importlib.import_module("server")
    return server
