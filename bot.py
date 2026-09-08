import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from dotenv import load_dotenv

from rubika_api import RubikaAPI
from telegram_api import TelegramAPI

load_dotenv()


def start_health_server() -> None:
    port = int(os.getenv("PORT", "8080"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("bot ok".encode("utf-8"))

        def log_message(self, format: str, *args) -> None:
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"سرویس سلامت روی پورت {port} روشن شد.")
    server.serve_forever()


def reply_text(text: str) -> str:
    text = (text or "").strip()
    if text in {"/start", "start", "شروع"}:
        return "سلام! ربات وصل است. یک پیام بفرست."
    if text in {"/help", "help", "راهنما"}:
        return "دستورها:\n/start شروع\n/help راهنما"
    if text:
        return f"پیامت را گرفتم: {text}"
    return "پیام متنی نبود، ولی ربات وصل است."


def extract_rubika_updates(data: dict) -> tuple[list, str | None]:
    if not isinstance(data, dict):
        return [], None
    updates = data.get("updates") or []
    next_offset = data.get("next_offset_id")
    return updates, next_offset


def handle_rubika_update(api: RubikaAPI, update: dict) -> None:
    if not isinstance(update, dict):
        return
    inner = update.get("update", update)
    chat_id = inner.get("chat_id")
    message = inner.get("new_message") or inner.get("message") or {}
    text = message.get("text", "")
    if chat_id:
        api.send_message(chat_id, reply_text(text))
        print("روبیکا:", text or "(بدون متن)")


def run_with_retry(name: str, runner) -> None:
    wait = 3
    while True:
        try:
            runner()
            return
        except PermissionError as error:
            print(name, ":", error)
            return
        except Exception as error:
            print(name, "قطع شد:", error)
            print(name, f": {wait} ثانیه دیگر دوباره وصل می‌شود...")
            time.sleep(wait)
            wait = min(wait * 2, 30)


def run_rubika(token: str) -> None:
    def start() -> None:
        api = RubikaAPI(token)
        me = api.get_me()
        print("روبیکا وصل شد:", me)
        offset_id = None
        while True:
            data = api.get_updates(offset_id=offset_id, limit=10)
            updates, next_offset = extract_rubika_updates(data)
            for update in updates:
                try:
                    handle_rubika_update(api, update)
                except Exception as error:
                    print("خطای پردازش روبیکا:", error)
            if next_offset:
                offset_id = next_offset
            time.sleep(2)

    run_with_retry("روبیکا", start)


def run_telegram(token: str, api_base: str) -> None:
    def start() -> None:
        api = TelegramAPI(token, api_base=api_base)
        me = api.get_me()
        print("تلگرام وصل شد:", me)
        offset = None
        while True:
            updates = api.get_updates(offset=offset)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                text = message.get("text", "")
                if chat_id:
                    api.send_message(chat_id, reply_text(text))
                    print("تلگرام:", text or "(بدون متن)")

    run_with_retry("تلگرام", start)


def main() -> None:
    rubika_token = os.getenv("RUBIKA_BOT_TOKEN", "").strip()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").strip()
    platform = os.getenv("BOT_PLATFORM", "both").strip().lower() or "both"

    threads = []
    if platform in {"both", "rubika"} and rubika_token:
        threads.append(Thread(target=run_rubika, args=(rubika_token,), daemon=True))
    if platform in {"both", "telegram"} and telegram_token:
        threads.append(Thread(target=run_telegram, args=(telegram_token, telegram_base), daemon=True))

    if not threads:
        print("هیچ توکنی پیدا نشد.")
        print("در Railway از بخش Variables توکن را بگذار.")
        print("توکن را داخل گیت‌هاب نگذار.")
        raise SystemExit(1)

    health = Thread(target=start_health_server, daemon=True)
    health.start()

    print("ربات در حال اجراست. برای توقف Ctrl+C بزن.")
    for thread in threads:
        thread.start()
    try:
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nربات متوقف شد.")


if __name__ == "__main__":
    main()
