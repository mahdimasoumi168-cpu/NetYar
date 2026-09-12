"""Production entrypoint shared by Railway and local execution."""
import os
import sys

import telegram_runtime_clean
sys.modules["telegram_runtime"] = telegram_runtime_clean

import uvicorn
import server

import production_stability
production_stability.install()

# Telegram recovery watchdog: keeps the single long-polling updater alive.
import telegram_reliability_fix
telegram_reliability_fix.install()

# Normalize Rubika sender/chat identities and make first contact reliable.
import rubika_stability_fix
rubika_stability_fix.install()

# Keep exactly one Rubika polling implementation.
import rubika_reliability_fix
rubika_reliability_fix.install()

# Final Rubika hardening: reliable inline buttons and no semantic dropping of
# legitimate repeated clicks.
import rubika_final_hardening
rubika_final_hardening.install()

# Continuous free-form partner/admin conversation on Rubika.
import rubika_ticket_chat
rubika_ticket_chat.install()

# Never let the webhook path and polling path process the same Rubika update.
import rubika_webhook_guard
rubika_webhook_guard.install()

# Final cross-platform layer MUST run after all legacy Rubika wrappers so a
# handled ticket message cannot fall through into older routers and duplicate
# or garble the response.
import cross_platform_stability_final
cross_platform_stability_final.install()


def main():
    uvicorn.run(
        server.api,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        lifespan="on",
    )


if __name__ == "__main__":
    main()
