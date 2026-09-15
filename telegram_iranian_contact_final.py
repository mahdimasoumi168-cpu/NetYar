"""Final Telegram Iranian menu contact option and routing guard."""
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, filters

CONTACT_USERNAME = os.getenv("CONTACT_USERNAME", "Good_ok_2000").strip().lstrip("@") or "Good_ok_2000"
CONTACT_BUTTON = "📞 تماس با ما"


def install(app, B):
    if getattr(B, "_iranian_contact_final", False):
        return

    old_main = B.main
    old_router = B.router

    def main(uid):
        st = B.S.get(uid, {})
        if st.get("status") == "iranian":
            rows = [
                ["🎫 پیگیری", "👥 پنل همکاران"],
                [CONTACT_BUTTON],
                ["🔄 شروع مجدد"],
            ]
            if B.admin(uid):
                rows.append(["🛠 پنل مدیریت بات"])
            return B.kb(rows)
        return old_main(uid)

    B.main = main

    async def router(update, context):
        message = getattr(update, "message", None)
        text = str(getattr(message, "text", "") or "").strip()
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("status") == "iranian" and text == CONTACT_BUTTON:
            url = f"https://t.me/{CONTACT_USERNAME}"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("📞 ارتباط با پشتیبانی", url=url)]])
            return await message.reply_text(
                "📞 تماس با ما\n\nبرای ارتباط با پشتیبانی روی دکمه زیر بزنید:",
                reply_markup=markup,
            )
        return await old_router(update, context)

    B.router = router
    B._iranian_contact_final = True
