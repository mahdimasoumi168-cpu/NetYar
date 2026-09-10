# Simulating URL resolution from the deployment
import sys
domain = "netyar-live-production.up.railway.app"
base = f"https://{domain}"
tg_url = f"{base}/telegram/update"
rb_url = f"{base}/rubika/update"
print(f"Resolved Telegram URL: {tg_url}")
print(f"Resolved Rubika URL: {rb_url}")
