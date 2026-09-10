import os, time, logging, re, json, requests
from core import db, now, check_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("netyar.rubika.v2")
TOKEN = os.getenv("RUBIKA_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("RUBIKA_BOT_TOKEN is missing")
BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"
HTTP = requests.Session()
HTTP.headers.update({"Content-Type": "application/json"})
ADMIN_IDS = {x.strip() for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip()}
ADMIN_COMMAND = os.getenv("ADMIN_COMMAND", "/Admin2025").strip()
CANCEL, OK = "❌ انصراف", "✅ تأیید"
STATE, OFFSET = {}, None
# Keep the existing file unchanged except for the partner password field fix.
