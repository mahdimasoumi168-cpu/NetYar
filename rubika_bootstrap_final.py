"""Final isolated Rubika startup bootstrap.

Rubika is deliberately isolated from Telegram. This bootstrap installs the
Rubika routing/hardening layers and then registers one HTTP webhook endpoint.
"""
import logging

log = logging.getLogger("netyar.rubika.bootstrap")

# Keep Rubika deployment changes observable as a single, deterministic layer.
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
            log.exception("Rubika compatibility layer failed: %s", name)


def _install_send_boundary_guard(rb):
    """Normalise every legacy row shape before the final sender sees it."""
    if getattr(rb, "_netyar_send_boundary_guard", False):
        return
    original_send = rb.send

    def normalise(rows):
        out = []
        for row in rows or []:
            if isinstance(row, (tuple, list)) and len(row) == 2 and not isinstance(row[0], (tuple, list, dict)):
                out.append([(str(row[0]), str(row[1]))])
                continue
            fixed = []
            for item in row or []:
                if isinstance(item, dict):
                    fixed.append(item)
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    fixed.append((str(item[0]), str(item[1])))
                else:
                    fixed.append((str(len(fixed)), str(item)))
            out.append(fixed)
        return out

    def guarded_send(chat, text, rows=None):
        return original_send(chat, text, normalise(rows) if rows else rows)

    rb.send = guarded_send
    rb._netyar_send_boundary_guard = True
    log.info("Rubika send boundary guard installed")


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
            _install_send_boundary_guard(rb)

            endpoint = server_module.public_url("/rubika/update")
            result = rb.call(
                "updateBotEndpoints",
                {"url": endpoint, "type": "ReceiveUpdate"},
            )
            server_module.rubika_ready = True
            log.info("Rubika final webhook registered: %s", result)
        except Exception:
            server_module.rubika_ready = False
            log.exception("Rubika final bootstrap failed; Telegram was left untouched")

    server_module._initialize_integrations = initialize_with_rubika
    server_module._netyar_rubika_bootstrap_final = True
    log.info("Rubika final bootstrap installed")
