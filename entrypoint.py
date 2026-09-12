"""Production entrypoint shared by Railway and local execution."""
import os
import sys

import telegram_runtime_clean
sys.modules["telegram_runtime"] = telegram_runtime_clean

import uvicorn
import server

import production_stability
production_stability.install()

import telegram_reliability_fix
telegram_reliability_fix.install()

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

# Exact-price mode is loaded after the legacy partner pricing module and after
# the full admin panel, so the administrator can enter the final amount directly.
import partner_price_exact
import rubika_v2 as _rubika
partner_price_exact.install_rubika(_rubika)

# Last-mile navigation is deliberately loaded last.
import rubika_navigation_stability
rubika_navigation_stability.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
