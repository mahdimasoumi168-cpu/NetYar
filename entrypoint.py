"""Production entrypoint for Railway and local execution."""
import os
import logging
import uvicorn
import server
import bale_bootstrap
import rubika_bootstrap_final
import production_stability

bale_bootstrap.install(server)
rubika_bootstrap_final.install(server)
production_stability.install()


def _install_before_telegram_start(app, B, log):
    """Install final Telegram ownership layers before polling starts."""
    pre_app_modules = (
        "telegram_partner_logout_fix",
        "telegram_language_consistency",
        "telegram_cancel_policy",
    )
    for module_name in pre_app_modules:
        try:
            module = __import__(module_name)
            module.install(B)
            log.info("telegram pre-build layer installed: %s", module_name)
        except Exception:
            log.exception("telegram pre-build layer unavailable: %s", module_name)

    app_modules = (
        # Highest-priority deterministic owner for partner login and management
        # communication. It must run before every legacy text router.
        "telegram_universal_partner_guard",
        "final_stability_overlay",
        "final_government_payment_overlay",
        "telegram_price_dedup_guard",
        "telegram_final_layer_loader",
        "telegram_government_flow_runtime_fix",
        "telegram_night_logout_final",
        "telegram_partner_login_fix",
        "telegram_offhours_partner_gate_v2",
        "telegram_admin_plus",
        "telegram_admin_power",
        "telegram_final_admin_menu_fix",
        "telegram_final_ops_overlay",
        "telegram_button_stability_final",
        "telegram_service_billing_v3_fix",
        "telegram_partner_ui_fix",
        "telegram_request_control_v2",
        "telegram_government_family_code_fix",
        "telegram_ui_policy_v2",
        "telegram_absolute_fix",
        "telegram_context_recovery",
        "telegram_operational_continuation_guard",
        "telegram_admin_request_reliability_fix",
        "telegram_partner_chat_reliability",
        "telegram_final_notification_reliability",
        "telegram_final_admin_partner_fix",
        "telegram_final_menu_dedup_guard",
    )
    for module_name in app_modules:
        try:
            module = __import__(module_name)
            module.install(app, B)
            log.info("telegram pre-polling layer installed: %s", module_name)
        except Exception:
            log.exception("telegram pre-polling layer unavailable: %s", module_name)


try:
    import telegram_runtime_clean as _telegram_runtime
    import bot as _telegram_bot
    if not getattr(_telegram_runtime, "_netyar_pre_polling_wrapper", False):
        _original_telegram_build = _telegram_runtime.build

        def _wrapped_telegram_build():
            app = _original_telegram_build()
            _install_before_telegram_start(app, _telegram_bot, logging.getLogger("netyar.entrypoint"))
            return app

        _telegram_runtime.build = _wrapped_telegram_build
        _telegram_runtime._netyar_pre_polling_wrapper = True
except Exception:
    logging.getLogger("netyar.entrypoint").exception("Telegram pre-polling bootstrap wrapper unavailable")


def main():
    uvicorn.run(server.api, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), lifespan="on")


if __name__ == "__main__":
    main()
