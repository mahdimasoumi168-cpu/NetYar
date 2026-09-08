import os

from dotenv import load_dotenv

from rubika_api import RubikaAPI
from telegram_api import TelegramAPI

load_dotenv()


def main() -> None:
    rubika_token = os.getenv("RUBIKA_BOT_TOKEN", "").strip()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").strip()

    if rubika_token:
        try:
            info = RubikaAPI(rubika_token).get_me()
            print("روبیکا OK:", info)
        except Exception as error:
            print("روبیکا خطا:", error)
    else:
        print("توکن روبیکا گذاشته نشده.")

    if telegram_token:
        try:
            info = TelegramAPI(telegram_token, api_base=telegram_base).get_me()
            print("تلگرام OK:", info)
        except Exception as error:
            print("تلگرام خطا:", error)
    else:
        print("توکن تلگرام گذاشته نشده.")


if __name__ == "__main__":
    main()
