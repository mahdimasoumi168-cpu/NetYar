import os, asyncio, logging, threading
from netyar.telegram_bot import build as build_telegram
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

def main():
    app=build_telegram()
    # Rubika is isolated in its own thread; an SDK/network problem there cannot stop Telegram.
    if os.getenv("RUBIKA_BOT_TOKEN","").strip():
        from netyar.rubika import start_thread
        threading.Thread(target=start_thread,name="rubika-bot",daemon=True).start()
    logging.info("NetYar started. Telegram=ON, Rubika=%s", "ON" if os.getenv("RUBIKA_BOT_TOKEN","").strip() else "OFF")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
