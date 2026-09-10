"""Security/logging hardening: never log HTTPX request URLs that can contain bot tokens."""
import logging

def install():
    # HTTPX INFO logs include complete request URLs. Telegram/Rubika API URLs may contain secrets.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("netyar.server").setLevel(logging.INFO)
