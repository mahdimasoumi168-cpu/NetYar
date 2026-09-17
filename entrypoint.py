"""NetYar production entrypoint.

The runtime layers are intentionally ordered: core guards first, service
flows in the middle, and final request/partner delivery layers last.
"""
import inspect
import logging
import os
import uvicorn
import bale_bootstrap
import production_stability
import rubika_bootstrap_final
import server
NETYAR_TELEGRAM_BUILD="2026-09-17-button-router-v5"
bale_bootstrap.install(server); rubika_bootstrap_final.install(server); production_stability.install()
PRE_TELEGRAM_MODULES=("telegram_global_cancel_v4","request_language_actions","telegram_partner_logout_fix","telegram_language_consistency","telegram_cancel_policy","telegram_offhours_absolute_start_guard")
TELEGRAM_MODULES=("telegram_admin_access_final_v1","telegram_government_phone_final","telegram_phone_registry_and_stability","telegram_final_hotfix_20260914","telegram_fast_response_layer","telegram_critical_input_logout_fix","telegram_idle_session_reset","telegram_input_continuation_guard","telegram_admin_button_guard","telegram_partner_pricing_stable","telegram_partner_session_persistence","telegram_management_destination_guard","telegram_global_admin_guard","telegram_universal_partner_guard","final_stability_overlay","final_government_payment_overlay","telegram_price_dedup_guard","telegram_government_flow_runtime_fix","telegram_offhours_api_fix","telegram_night_logout_final","telegram_partner_login_fix","telegram_offhours_partner_gate_v2","telegram_night_shift_stability_v26","telegram_admin_plus","telegram_partner_code_reliable","telegram_request_full_details_patch","telegram_request_details_fix","telegram_final_ops_overlay","telegram_button_stability_final","telegram_service_billing_v3_fix","telegram_partner_ui_fix","telegram_ux_billing","telegram_request_control_v2","telegram_government_family_code_fix","telegram_ui_policy_v2","telegram_absolute_fix","telegram_operational_continuation_guard","telegram_admin_request_reliability_fix","telegram_partner_chat_reliability","telegram_final_notification_reliability","telegram_final_admin_partner_fix","telegram_final_menu_dedup_guard","telegram_final_user_state_guard","telegram_service_dispatch_final","telegram_information_input_final","telegram_input_hardening_v3","full_admin_control_patch","production_final_patch","telegram_announcement_media","government_balance_postal_fix","telegram_admin_menu_restore","telegram_request_workflow_final","telegram_universal_button_guard","telegram_final_repair","telegram_irancell_partner_service","telegram_government_cancel_fix","telegram_government_documents_v3","telegram_government_validation_final","telegram_management_stability_final","telegram_final_ui_rebind","telegram_final_partner_panel","telegram_final_integration_guard","telegram_partner_menu_final_v2","telegram_partner_actions_final_guard","telegram_partner_ticket_fix","telegram_ticket_reliability","telegram_ticket_media","telegram_government_final_override_v18","telegram_final_request_delivery_v17","telegram_final_requirements_guard_v1")
def _install_module(name,app,bot,logger,*,pre=False):
    try:
        module=__import__(name); fn=getattr(module,"install",None)
        if not callable(fn): raise AttributeError("install() not found")
        sig=inspect.signature(fn); positional=[p for p in sig.parameters.values() if p.kind in (inspect.Parameter.POSITIONAL_ONLY,inspect.Parameter.POSITIONAL_OR_KEYWORD)]; required=[p for p in positional if p.default is inspect.Parameter.empty]
        if len(required)>=2 or len(positional)>=2: fn(app,bot)
        elif len(required)==1 or len(positional)==1: fn(bot)
        else: fn()
        logger.info("Telegram %s layer installed: %s","pre-build" if pre else "runtime",name)
    except Exception: logger.exception("Telegram %s layer unavailable: %s","pre-build" if pre else "runtime",name)
def _install_telegram_layers(app,bot,logger):
    for name in PRE_TELEGRAM_MODULES: _install_module(name,app,bot,logger,pre=True)
    for name in TELEGRAM_MODULES: _install_module(name,app,bot,logger)
    for name in ("telegram_government_strict_validation","telegram_government_flow_hardening_v4","telegram_government_v3_balance_guard","telegram_government_final_flow_v7","telegram_request_code_image_flow_v4","telegram_customer_code_request_v1","telegram_final_bugfixes_v1"): _install_module(name,app,bot,logger)
    for name in ("telegram_partner_management_hotfix_v25","telegram_partner_runtime_hardening_v26","telegram_partner_main_guard","telegram_partner_service_continuation_v27"): _install_module(name,app,bot,logger)
    try:
        from telegram_request_full_details_patch import finalize; finalize(bot); logger.info("Telegram complete-request notification finalizer installed")
    except Exception: logger.exception("Telegram complete-request notification finalizer unavailable")
    for name in ("desktop_agent_api_clean","telegram_partner_final_router_v29","telegram_partner_logout_hardening_v31","telegram_absolute_callback_hardening_v30","telegram_partner_navigation_final_v32","telegram_partner_navigation_final_v33","telegram_final_admin_navigation_v3","iranian_menu_patch","telegram_enamad_trust","telegram_final_unified_router_v34","telegram_request_action_bridge_v35","telegram_final_iranian_menu_v37","telegram_final_iranian_menu_v38","telegram_ui_universal_hotfix_v40","telegram_ui_absolute_owner_v41","telegram_ui_absolute_owner_v42","telegram_ui_absolute_owner_v43","telegram_universal_callback_owner_v46","telegram_final_requirements_guard_v1","telegram_admin_button_final_v1"): _install_module(name,app,bot,logger)
    _install_module("telegram_admin_ui_final_v2",app,bot,logger)
    # Canonical reply-keyboard owner must be installed before the final text
    # router so B.main/B.router are the deterministic implementations used by
    # the last text-button layer. Without this layer, several main/partner
    # buttons can fall back to competing legacy routers.
    _install_module("canonical_button_router",app,bot,logger)
    _install_module("telegram_final_text_router_v1",app,bot,logger)
def main():
    logger=logging.getLogger("netyar.entrypoint"); logger.info("NetYar Telegram build=%s",NETYAR_TELEGRAM_BUILD); uvicorn.run(server.api,host="0.0.0.0",port=int(os.getenv("PORT","8000")),lifespan="on")
if __name__=="__main__": main()
