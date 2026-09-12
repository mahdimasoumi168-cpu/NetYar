"""Last runtime guard for Telegram/Rubika navigation and transport."""
import asyncio
import logging
import threading
import time

log = logging.getLogger("netyar.last_messenger_stability")

ADMIN_LABELS = {
    "🛠 پنل مدیریت بات", "🛠 پنل مدیریت",
    "👤 کاربران", "👤 پنل کاربران", "👥 همکاران", "🤝 همکاران",
    "➕ افزودن همکار", "💰 شارژها", "💰 پرداخت‌های مشتری",
    "📋 درخواست‌ها", "⚙️ قیمت‌ها", "🟢 خدمات", "📊 گزارش کامل", "📊 گزارش",
    "📣 اعلان همگانی", "🤖 بات‌های متصل", "➕ افزودن بات", "🧾 لاگ مدیریت",
    "⚙️ تنظیمات سیستم", "⚙️ تنظیمات پایه", "🎫 تیکت‌ها",
    "🟢/🔴 خدمات ایرانی", "🟢/🔴 خدمات اتباع", "💰 قیمت خدمات", "📝 تغییر متن‌ها",
    "📎 مدارک و فایل‌ها", "👤 مدیران", "🤖 پیام‌رسان‌ها", "📊 گزارش‌ها",
    "📞 پشتیبانی", "⬅️ منوی اصلی", "⬅️ بازگشت",
}


def _callback_update(q):
    class Msg:
        def __init__(self, original):
            self._original = original
            self.chat = getattr(original, "chat", None)
            self.from_user = q.from_user
            self.text = getattr(original, "text", "")

        async def reply_text(self, *args, **kwargs):
            return await q.message.reply_text(*args, **kwargs)

    class U:
        effective_user = q.from_user
        message = Msg(q.message)
        effective_message = q.message
        callback_query = q

    return U()


def install():
    # Telegram: final_platform_fix uses ik:* callbacks, while the later
    # universal layer only knows ui:* tokens. Dispatch ik:* directly here.
    try:
        import bot as B
        import final_platform_fix as P
        from telegram.ext import CallbackQueryHandler

        if not getattr(B, "_last_messenger_telegram_guard", False):
            actions = getattr(P, "_actions", {})

            async def ik_guard(update, context):
                q = update.callback_query
                label = str(actions.get(str(q.data or ""), "")).strip()
                await q.answer()
                if not label:
                    return

                # Admin callbacks must never fall through to the generic
                # customer router. That was the source of «گزینه مدیریت
                # شناخته نشد» after opening the admin panel.
                if B.admin(q.from_user.id) and label in ADMIN_LABELS:
                    try:
                        await P._remove_old_telegram_keyboard(q.message)
                    except Exception:
                        pass
                    handler = getattr(B, "admin_text", None)
                    if handler is not None:
                        return await handler(_callback_update(q), context)

                if label in {"👥 پنل همکاران", "🔵 👥 پنل همکاران", "🔵 👥 Partner panel", "🔵 👥 لوحة الشركاء"}:
                    try:
                        await P._remove_old_telegram_keyboard(q.message)
                    except Exception:
                        pass
                    return await B.partner(_callback_update(q), context)

                if label in {B.CANCEL, "❌ لغو", "Cancel", "إلغاء"}:
                    return await B.cancel(_callback_update(q), context)

                return await P._inline_text_callback(update, context)

            old_build = B.build
            def build_with_last_guard():
                app = old_build()
                app.add_handler(CallbackQueryHandler(ik_guard, pattern=r"^ik:"), group=0)
                return app
            B.build = build_with_last_guard
            B._last_messenger_telegram_guard = True
            log.info("Last Telegram ik callback/admin/navigation guard installed")
    except Exception:
        log.exception("Telegram last guard failed")

    # Rubika: use the native chat_keypad format and do not repeatedly register
    # the endpoint. The deployed service already receives NewMessage updates;
    # repeated endpoint registration was the source of InvalidUrl startup noise.
    try:
        import rubika_v2 as RB
        if not getattr(RB, "_last_messenger_rubika_guard", False):
            lock = threading.Lock()
            last_send = [0.0]

            def stable_send(chat, text, r=None):
                payload = {"chat_id": str(chat), "text": str(text)}
                if r:
                    payload.update(
                        chat_keypad_type="New",
                        chat_keypad={"rows": RB.rows(r), "resize_keyboard": True, "one_time_keyboard": False},
                    )
                last_error = None
                for attempt in range(3):
                    try:
                        with lock:
                            wait = 3.0 - (time.monotonic() - last_send[0])
                            if wait > 0:
                                time.sleep(wait)
                            last_send[0] = time.monotonic()
                        response = RB.HTTP.post(f"{RB.BASE}/sendMessage", json=payload, timeout=30)
                        response.raise_for_status()
                        data = response.json()
                        if isinstance(data, dict) and data.get("status") == "TOO_REQUESTS":
                            last_error = RuntimeError("TOO_REQUESTS")
                            time.sleep(6.0 + attempt * 4.0)
                            continue
                        return data
                    except Exception as exc:
                        last_error = exc
                        if attempt < 2:
                            time.sleep(4.0 + attempt * 3.0)
                log.error("Rubika stable send failed: %s", last_error)
                return {"status": "RETRY_LATER", "error": str(last_error or "send failed")}

            old_call = RB.call
            def stable_call(method, p=None):
                if method == "updateBotEndpoints":
                    log.info("Rubika endpoint registration skipped; using existing receive endpoint/polling")
                    return {"status": "OK", "data": {"skipped": True}}
                return old_call(method, p)

            RB.send = stable_send
            RB.call = stable_call
            RB._last_messenger_rubika_guard = True
            log.info("Last Rubika native transport/rate guard installed")
    except Exception:
        log.exception("Rubika last guard failed")
