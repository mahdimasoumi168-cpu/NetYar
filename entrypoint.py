"""Production entrypoint shared by Railway and local execution."""
import os
import sys

import telegram_runtime_clean
sys.modules["telegram_runtime"] = telegram_runtime_clean

import uvicorn
import server

# Telegram lifecycle: keep ONE authoritative recovery mechanism.
# The older telegram_reliability_fix wrapped _initialize_integrations a second
# time and created a competing recovery path. The single-poller guard below is
# now the only Telegram recovery owner.
import production_stability
production_stability.install()

import telegram_single_poller_guard
telegram_single_poller_guard.install()

import rubika_stability_fix
rubika_stability_fix.install()

import rubika_reliability_fix
rubika_reliability_fix.install()

import rubika_final_hardening
rubika_final_hardening.install()

import rubika_ticket_chat
rubika_ticket_chat.install()

import rubika_webhook_guard
rubika_webhook_guard.install()

import cross_platform_stability_final
cross_platform_stability_final.install()

import partner_price_exact
import rubika_v2 as _rubika
partner_price_exact.install_rubika(_rubika)

import rubika_navigation_stability
rubika_navigation_stability.install()

# Must be last: server._patch_rubika runs again when a webhook arrives.
import rubika_final_button_router
rubika_final_button_router.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
