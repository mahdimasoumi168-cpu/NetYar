"""Final isolated Rubika startup bootstrap.

Rubika is deliberately isolated from Telegram. This bootstrap installs the
Rubika routing/hardening layers and then registers one HTTP webhook endpoint.
"""
import logging

log = logging.getLogger("netyar.rubika.bootstrap")


_RUBIKA_LAYERS = (
    "rubika_fix",
    "rubika_core_compat",
    "rubika_runtime_fix",
    "rubika_final_router",
    "rubika_final_button_router",
    "rubika_button_guard",
    "rubika_dispatch_fix",
    "rubika_stability_fix",
    "rubika_final_hardening",
    "rubika_final_stability",
)


def _install_layers(rb):
    for name in _RUBIKA_LAYERS:
        try:
            mod = __import__(name)
            fn = getattr(mod, "install", None)
            if callable(fn):
                try:
                    fn()
                except TypeError:
                    fn(rb)
                log.info("Rubika compatibility layer installed: %s", name)
        except ModuleNotFoundError:
            log.warning("Rubika optional layer not found: %s", name)
        except Exception:
            # One compatibility shim must never prevent the bot from starting.
            log.exception("Rubika compatibility layer failed: %s", name)


def install(server_module):
    if getattr(server_module, "_netyar_rubika_bootstrap_final", False):
        return

    original = server_module._initialize_integrations

    async def initialize_with_rubika():
        # Keep Telegram's existing startup path completely untouched.
        await original()
        try:
            import rubika_v2 as rb
            _install_layers(rb)

            endpoint = server_module.public_url("/rubika/update")
            result = rb.call(
                "updateBotEndpoints",
                {"url": endpoint, "type": "ReceiveUpdate"},
            )
            server_module.rubika_ready = True
            log.info("Rubika final webhook registered: %s", result)
        except Exception:
            server_module.rubika_ready = False
            # Rubika failure is isolated; do not change Telegram state.
            log.exception("Rubika final bootstrap failed; Telegram was left untouched")

    server_module._initialize_integrations = initialize_with_rubika
    server_module._netyar_rubika_bootstrap_final = True
    log.info("Rubika final bootstrap installed")
