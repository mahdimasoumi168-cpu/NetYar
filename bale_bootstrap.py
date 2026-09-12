"""Install the Bale adapter without coupling Bale lifecycle to Telegram/Rubika."""
import asyncio
import json
import logging

from bale_runtime import BaleRuntime
from core import db

log = logging.getLogger("netyar.bale_bootstrap")


def install(server):
    if getattr(server, "_bale_bootstrap_installed", False):
        return

    runtime = BaleRuntime("", "")
    server.bale_runtime = runtime
    server.bale_ready = False

    @server.api.get("/bale/update")
    async def bale_update_probe():
        return {"ok": True, "service": "NetYar", "provider": "bale"}

    @server.api.post("/bale/update")
    async def bale_update(request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                return {"ok": True}
            await runtime.handle_update(body, db)
            return {"ok": True}
        except Exception:
            log.exception("Bale webhook update failed")
            return {"ok": False, "error": "bale_update_failed"}

    original_initialize = server._initialize_integrations

    async def initialize_with_bale():
        await original_initialize()
        try:
            server.bale_ready = await runtime.start(db, server.public_url)
        except Exception:
            log.exception("Bale initialization failed")
            server.bale_ready = False

    server._initialize_integrations = initialize_with_bale
    server._bale_bootstrap_installed = True
    log.info("Bale bootstrap installed")
