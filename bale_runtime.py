"""Small dependency-free Bale adapter for NetYar.

Bale uses a Telegram-compatible Bot API endpoint. This adapter deliberately
keeps its own state and only depends on requests, so Telegram/Rubika startup
cannot be broken by a missing Bale package.
"""
import asyncio
import logging
import os
import requests
from core import now

log = logging.getLogger("netyar.bale")
BASE = "https://tapi.bale.ai/bot{}"


class BaleRuntime:
    def __init__(self, token, base_url):
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.ready = False

    def call(self, method, payload=None):
        url = f"{self.base_url}/{method}"
        r = requests.post(url, json=payload or {}, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok", True):
            raise RuntimeError(f"Bale API {method} failed: {data}")
        return data

    def send_message(self, chat_id, text, reply_markup=None):
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.call("sendMessage", payload)

    def set_webhook(self, url):
        return self.call("setWebhook", {"url": url})

    def _token_from_db(self, db):
        try:
            row = db.conn.execute(
                "SELECT token_ref FROM bot_integrations WHERE platform='bale' AND token_ref<>'' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return str(row[0]).strip() if row else ""
        except Exception:
            log.exception("Cannot read Bale token from database")
            return ""

    async def start(self, db, public_url):
        token = os.getenv("BALE_BOT_TOKEN", "").strip() or self._token_from_db(db)
        if not token:
            log.warning("Bale is not configured: set BALE_BOT_TOKEN or add a Bale bot in admin")
            return False
        self.token = token
        self.base_url = BASE.format(token)
        try:
            me = await asyncio.to_thread(self.call, "getMe")
            endpoint = public_url("/bale/update")
            await asyncio.to_thread(self.set_webhook, endpoint)
            db.conn.execute("UPDATE bot_integrations SET active=1,status='active',updated_at=? WHERE platform='bale'", (now(),))
            db.conn.commit()
            self.ready = True
            log.info("Bale webhook active: bot=%s endpoint=%s", me.get("result", {}).get("username", "-"), endpoint)
            return True
        except Exception:
            log.exception("Bale startup failed")
            self.ready = False
            return False

    async def handle_update(self, update, db):
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        text = str(msg.get("text") or "").strip()
        if text in {"/start", "/restart", "شروع"}:
            keyboard = {"keyboard": [["🇮🇷 فارسی", "🇬🇧 English", "🇸🇦 العربية"]], "resize_keyboard": True}
            await asyncio.to_thread(self.send_message, chat_id, "سلام و خوش آمدید 🌷\nلطفاً زبان را انتخاب کنید:", keyboard)
            return
        if text in {"🇮🇷 فارسی", "فارسی"}:
            keyboard = {"keyboard": [["🪪 اتباع هستم", "🇮🇷 ایرانی هستم"]], "resize_keyboard": True}
            await asyncio.to_thread(self.send_message, chat_id, "زبان فارسی فعال شد.\nلطفاً نوع کاربر را انتخاب کنید:", keyboard)
            return
        if text in {"🇬🇧 English", "English"}:
            keyboard = {"keyboard": [["🪪 I am a foreign citizen", "🇮🇷 I am Iranian"]], "resize_keyboard": True}
            await asyncio.to_thread(self.send_message, chat_id, "English is active.\nPlease choose your user type:", keyboard)
            return
        if text in {"🇸🇦 العربية", "العربية"}:
            keyboard = {"keyboard": [["🪪 أنا أجنبي", "🇮🇷 أنا إيراني"]], "resize_keyboard": True}
            await asyncio.to_thread(self.send_message, chat_id, "تم تفعيل العربية.\nيرجى اختيار نوع المستخدم:", keyboard)
            return
        if text in {"🪪 اتباع هستم", "اتباع هستم", "🪪 I am a foreign citizen", "🪪 أنا أجنبي"}:
            keyboard = {"keyboard": [["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"], ["🏛 حل مشکل ورود اتباع دولت من", "🎫 پیگیری"], ["📱 خدمات سیم کارت", "👥 پنل همکاران"]], "resize_keyboard": True}
            await asyncio.to_thread(self.send_message, chat_id, "خدمات اتباع:", keyboard)
            return
        if text in {"🇮🇷 ایرانی هستم", "ایرانی هستم", "🇮🇷 I am Iranian", "🇮🇷 أنا إيراني"}:
            keyboard = {"keyboard": [["👥 پنل همکاران"], ["🎫 پیگیری"]], "resize_keyboard": True}
            await asyncio.to_thread(self.send_message, chat_id, "فعلاً خدماتی برای ایرانی فعال نیست.\nپنل همکاران و پیگیری در دسترس است:", keyboard)
            return
        if text in {"❌ انصراف", "/cancel"}:
            await asyncio.to_thread(self.send_message, chat_id, "❌ عملیات لغو شد. برای شروع دوباره /start را بزنید.")
            return
        await asyncio.to_thread(self.send_message, chat_id, "❓ گزینه موردنظر پیدا نشد.\nبرای نمایش منوی اصلی /start را بزنید.")
