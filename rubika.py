"""Rubika adapter using the current Rubka SDK.

The business logic stays in netyar.core. This adapter intentionally has a small,
defensive surface so Rubika failures do not take down Telegram.
"""
import os, logging, asyncio
from .core import db
log=logging.getLogger("netyar.rubika")

async def run():
    token=os.getenv("RUBIKA_BOT_TOKEN","").strip()
    if not token:
        log.info("RUBIKA_BOT_TOKEN not set; Rubika adapter disabled.")
        return
    try:
        from rubka.asynco import Robot
    except Exception:
        try:
            from rubka import Robot
        except Exception as exc:
            log.exception("Rubka SDK import failed: %s",exc); return

    bot=Robot(token=token)

    @bot.on_message(commands=["start"])
    async def start_handler(bot, message):
        uid=str(message.sender_id)
        db.user(int(uid) if uid.isdigit() else abs(hash(uid)),"rubika",getattr(message,"username",""),getattr(message,"name",""))
        await message.reply(db.setting("welcome"))

    @bot.on_message()
    async def text_handler(bot, message):
        text=(getattr(message,"text","") or "").strip()
        uid=str(getattr(message,"sender_id",""))
        if text.startswith("/start"): return
        if text == "/admin":
            if db.is_admin("rubika",uid): await message.reply("🔐 پنل مدیریت روبیکا فعال است.")
            else: await message.reply("⛔ دسترسی ندارید.")
            return
        if text == "خدمات":
            rows=db.services(True)
            await message.reply("\n".join(f"{r['id']}. {r['name']} — {r['price']:,} تومان" for r in rows) or "خدمتی فعال نیست.")
            return
        await message.reply("درخواست شما دریافت شد. برای ادامه از منوی خدمات استفاده کنید.")

    await bot.run()

def start_thread():
    asyncio.run(run())
