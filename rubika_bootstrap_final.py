"""Single-owner Rubika/Telegram integration bootstrap.

The previous version wrapped server._initialize_integrations and then called the
old function, which itself initialized Rubika. That caused Rubika layers and
updateBotEndpoints to run twice. This module is now the sole owner of the
integration startup path: Telegram is initialized once, then Rubika once.
"""
import asyncio
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

_RB_LOCKS = {}


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
    """Normalize legacy keypad row shapes before the Rubika API sender."""
    if getattr(rb, "_netyar_send_boundary_guard", False):
        return
    original_send = rb.send

    def normalise(rows):
        out = []
        for row in rows or []:
            # Legacy callers sometimes pass [button_id, label] instead of
            # [(button_id, label)]. Treat that as one button, not two buttons.
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


def _telegram_initializer(server_module):
    async def initialize_telegram_only():
        server_module.telegram_ready = False
        try:
            import telegram_runtime_clean as tg
            server_module.telegram_app = tg.build()
            await server_module.telegram_app.initialize()
            await server_module.telegram_app.start()
            await server_module.telegram_app.bot.delete_webhook(drop_pending_updates=False)
            updater = getattr(server_module.telegram_app, "updater", None)
            if updater is None:
                raise RuntimeError("python-telegram-bot updater is unavailable")
            if not getattr(updater, "running", False):
                await updater.start_polling(allowed_updates=None, drop_pending_updates=False)
            if not getattr(updater, "running", False):
                raise RuntimeError("Telegram polling did not enter running state")
            server_module.telegram_ready = True
            log.info("Telegram long polling started successfully")
        except Exception:
            log.exception("Telegram startup failed")
            server_module.telegram_ready = False

    return initialize_telegram_only


async def _run_rubika_serialized(update, rb, user_id):
    key = str(user_id or "unknown")
    lock = _RB_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        try:
            await asyncio.to_thread(rb.process, update)
            log.info("Rubika update processed: user=%s", key)
        except Exception:
            log.exception("Rubika background update processing failed: user=%s", key)


def install(server_module):
    if getattr(server_module, "_netyar_rubika_bootstrap_final", False):
        return

    async def initialize_with_single_owner():
        # Telegram is initialized exactly once here. We intentionally do not
        # call the old server initializer because it also initializes Rubika.
        await _telegram_initializer(server_module)()

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
            log.info("Rubika webhook registered exactly once: %s", result)
        except Exception:
            server_module.rubika_ready = False
            log.exception("Rubika startup failed; Telegram remains active")

    server_module._initialize_integrations = initialize_with_single_owner
    server_module._netyar_rubika_bootstrap_final = True
    log.info("Rubika single-owner bootstrap installed")
