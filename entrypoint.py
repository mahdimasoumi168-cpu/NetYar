"""Production entrypoint for Railway and local execution."""
import os
import logging
import inspect
import uvicorn
import server
import bale_bootstrap
import rubika_bootstrap_final
import production_stability

NETYAR_TELEGRAM_BUILD = "2026-09-14-final-routing-repair"

bale_bootstrap.install(server)
rubika_bootstrap_final.install(server)
production_stability.install()


def _install_before_telegram_start(app, B, log):
    pre_app_modules = ("request_language_actions", "telegram_partner_logout_fix", "telegram_language_consistency", "telegram_cancel_policy")

    def install_module(module_name, *, pre=False):
        try:
            module = __import__(module_name)
            installer = getattr(module, "install", None)
            if not callable(installer):
                raise AttributeError("install() not found")
            sig = inspect.signature(installer)
            positional = [p for p in sig.parameters.values() if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            required = [p for p in positional if p.default is inspect.Parameter.empty]
            if len(required) >= 2 or len(positional) >= 2:
                installer(app, B)
            elif len(required) == 1 or len(positional) == 1:
                installer(B)
            else:
                installer()
            log.info("telegram %s layer installed: %s", "pre-build" if pre else "pre-polling", module_name)
        except Exception:
            log.exception("telegram %s layer unavailable: %s", "pre-build" if pre else "pre-polling", module_name)

    for module_name in pre_app_modules:
        install_module(module_name, pre=True)

    app_modules = (
        "telegram_critical_input_logout_fix","telegram_idle_session_reset","telegram_input_continuation_guard",
        "telegram_admin_button_guard","telegram_partner_pricing_stable","telegram_partner_session_persistence",
        "telegram_management_destination_guard","telegram_global_admin_guard","telegram_universal_partner_guard",
        "final_stability_overlay","final_government_payment_overlay","telegram_price_dedup_guard",
        "telegram_government_flow_runtime_fix","telegram_night_logout_final","telegram_partner_login_fix",
        "telegram_offhours_partner_gate_v2","telegram_admin_plus","telegram_partner_code_reliable",
        "telegram_request_full_details_patch","telegram_request_details_fix","telegram_final_ops_overlay",
        "telegram_button_stability_final","telegram_service_billing_v3_fix","telegram_partner_ui_fix",
        "telegram_ux_billing","telegram_request_control_v2","telegram_government_family_code_fix",
        "telegram_ui_policy_v2","telegram_absolute_fix","telegram_operational_continuation_guard",
        "telegram_admin_request_reliability_fix","telegram_partner_chat_reliability","telegram_final_notification_reliability",
        "telegram_final_admin_partner_fix","telegram_final_menu_dedup_guard","telegram_final_user_state_guard",
        "telegram_service_dispatch_final","telegram_information_input_final","telegram_input_hardening_v3",
        "full_admin_control_patch","production_final_patch","telegram_announcement_media",
        "government_balance_postal_fix","telegram_admin_menu_restore","telegram_request_workflow_final",
        "telegram_universal_button_guard","telegram_final_repair",
    )
    for module_name in app_modules:
        install_module(module_name)

    try:
        from telegram_request_full_details_patch import finalize
        finalize(B)
        log.info("telegram complete-request notification finalizer installed")
    except Exception:
        log.exception("telegram complete-request notification finalizer unavailable")


try:
    import telegram_runtime_clean as _telegram_runtime
    import bot as _telegram_bot
    if not getattr(_telegram_runtime,"_netyar_pre_polling_wrapper",False):
        _original_telegram_build=_telegram_runtime.build
        def _wrapped_telegram_build():
            app=_original_telegram_build()
            _install_before_telegram_start(app,_telegram_bot,logging.getLogger("netyar.entrypoint"))
            return app
        _telegram_runtime.build=_wrapped_telegram_build
        _telegram_runtime._netyar_pre_polling_wrapper=True
except Exception:
    logging.getLogger("netyar.entrypoint").exception("Telegram pre-polling bootstrap wrapper unavailable")


def main():
    logging.getLogger("netyar.entrypoint").info("NetYar Telegram build=%s", NETYAR_TELEGRAM_BUILD)
    uvicorn.run(server.api,host="0.0.0.0",port=int(os.getenv("PORT","8000")),lifespan="on")


if __name__=="__main__":
    main()
