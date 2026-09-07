import os
import logging
from rubka.asynco import Robot, Message
from core import db, now

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
TOKEN = os.getenv("RUBIKA_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("RUBIKA_BOT_TOKEN environment variable is missing.")

rubika = Robot(token=TOKEN, safeSendMode=True, max_cache_size=2000, max_msg_age=120)
state = {}

CANCEL = "❌ انصراف"

def uid_of(message):
    return str(getattr(message, "sender_id", ""))

def name_of(message):
    return getattr(message, "first_name", None) or getattr(message, "username", None) or "کاربر"

def main_menu():
    return ("1) 🪪 فیدای غیر حضوری\n"
            "2) 🖨 خدمات چاپ\n"
            "3) 🪪 حل مشکل ورود اتباع سامانه دولت من\n"
            "4) 👥 پنل همکاران\n"
            "5) 🎫 پیگیری\n"
            "\n❌ انصراف")

async def show_language(message):
    state[uid_of(message)] = {"step": "language"}
    await message.reply("🌐 زبان را انتخاب کنید:\n1) فارسی\n2) English\n3) العربية")

@rubika.on_message(commands=["start"])
async def start(_: Robot, message: Message):
    uid = uid_of(message)
    if not uid: return
    db.user("rubika", uid, "", name_of(message))
    if db.setting("bot_open", "1") != "1":
        await message.reply("⏳ ربات موقتاً در حال بروزرسانی است.")
        return
    await show_language(message)

@rubika.on_message()
async def all_messages(_: Robot, message: Message):
    uid = uid_of(message)
    text = (getattr(message, "text", "") or "").strip()
    if not uid: return
    internal_id = db.user("rubika", uid, "", name_of(message))
    if text in ("/start", "شروع"):
        await show_language(message); return
    if text == CANCEL:
        state.pop(uid, None)
        await message.reply("عملیات لغو شد.\n\n" + main_menu()); return
    if db.setting("bot_open", "1") != "1":
        await message.reply("⏳ ربات موقتاً در حال بروزرسانی است."); return

    st = state.get(uid, {})
    step = st.get("step")
    if step == "language":
        if text not in ("1", "2", "3", "فارسی", "English", "العربية"):
            await message.reply("لطفاً یکی از سه زبان را انتخاب کنید."); return
        st["language"] = text
        st["step"] = "citizenship"
        await message.reply("آیا اتباع هستید یا ایرانی؟\n1) اتباع\n2) ایرانی\n\n" + CANCEL); return
    if step == "citizenship":
        if text in ("2", "ایرانی"):
            st["citizenship"] = "iranian"; st["step"] = None
            await message.reply("فعلاً خدماتی برای ایرانی فعال نیست.\n\n👥 پنل همکاران\n🎫 پیگیری\n\n" + CANCEL); return
        if text not in ("1", "اتباع"):
            await message.reply("لطفاً اتباع یا ایرانی را انتخاب کنید."); return
        st["citizenship"] = "foreign"; st["step"] = "menu"
        await message.reply("خدمات موردنظر را انتخاب کنید:\n\n" + main_menu()); return

    if text in ("1", "🪪 فیدای غیر حضوری"):
        st["step"] = "fida_id"
        await message.reply("🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.\n\n" + CANCEL); return
    if text in ("2", "🖨 خدمات چاپ"):
        st["step"] = "print_color"
        await message.reply("🖨 نوع چاپ را انتخاب کنید:\n1) سیاه و سفید\n2) رنگی\n\n" + CANCEL); return
    if text in ("3", "🪪 حل مشکل ورود اتباع سامانه دولت من"):
        st["step"] = "gov_fida"
        await message.reply("شناسه فیدای مشترک را وارد کنید.\n\n" + CANCEL); return
    if text in ("4", "👥 پنل همکاران"):
        st["step"] = "partner_phone"
        await message.reply("📱 شماره همراه همکار را وارد کنید.\n\n" + CANCEL); return
    if text in ("5", "🎫 پیگیری", "پیگیری"):
        st["step"] = "track"
        await message.reply("🎫 کد پیگیری را وارد کنید.\n\n" + CANCEL); return

    if step == "track":
        r = db.conn.execute("SELECT * FROM requests WHERE tracking_code=?", (text,)).fetchone()
        state.pop(uid, None)
        if r: await message.reply(f"🎫 کد پیگیری: {text}\nوضعیت: {r['status']}")
        else: await message.reply("❌ کد پیگیری پیدا نشد.")
        return
    if step == "gov_fida":
        st["fida"] = text; st["step"] = "gov_yekta"
        await message.reply("شناسه یکتای مشترک را وارد کنید.\n\n" + CANCEL); return
    if step == "gov_yekta":
        st["yekta"] = text; st["step"] = "gov_id"
        await message.reply("تصویر مدرک شناسایی مشترک را ارسال کنید.\n\n" + CANCEL); return
    if step == "gov_id":
        st["step"] = "gov_sim"
        await message.reply("📱 شماره موبایل مشترک را وارد کنید.\nسیم‌کارت باید به نام خود مشترک باشد.\n\n" + CANCEL); return
    if step == "gov_sim":
        st["phone"] = text; st["step"] = "gov_carddoc"
        await message.reply("در صورت داشتن سند سیم‌کارت، تصویر آن را ارسال کنید؛ در غیر این صورت «ندارم» بنویسید.\n\n" + CANCEL); return
    if step == "gov_carddoc":
        svc = db.service("government")
        amount = int(svc["price"] if svc else 500000)
        st["step"] = "gov_confirm"; st["amount"] = amount
        await message.reply(f"💳 هزینه خدمات: {amount:,} تومان\n\nبرای ادامه «تأیید» و برای لغو «انصراف» را بزنید.\n\n{CANCEL}"); return
    if step == "print_color":
        st["color"] = text; st["step"] = "print_side"
        await message.reply("چاپ را انتخاب کنید:\n1) یک‌رو\n2) پشت‌ورو\n\n" + CANCEL); return
    if step == "print_side":
        st["side"] = text; st["step"] = "print_count"
        await message.reply("تعداد نسخه موردنیاز از هر صفحه را وارد کنید.\n\n" + CANCEL); return
    if step == "print_count":
        if not text.isdigit(): await message.reply("تعداد را به صورت عدد وارد کنید."); return
        st["count"] = int(text); st["step"] = "print_files"
        await message.reply("📎 حالا فایل‌ها یا عکس‌های موردنظر را ارسال کنید.\nبعد از ارسال همه فایل‌ها، «تأیید» را بزنید.\n\n" + CANCEL); return
    if step in ("fida_id", "print_files"):
        if text in ("تأیید", "تایید"):
            key = "fida" if step == "fida_id" else "print"
            svc = db.service(key); amount = int(svc["price"] if svc else 0)
            st["step"] = "confirm"; st["amount"] = amount
            await message.reply(f"💳 مبلغ قابل پرداخت: {amount:,} تومان\n\nبرای ادامه «تأیید» را بزنید.\n{CANCEL}"); return
        st["last"] = text
        await message.reply("✅ دریافت شد. اگر فایل/مدرک دیگری دارید ارسال کنید؛ در پایان «تأیید» را بزنید.\n\n" + CANCEL); return
    if step in ("confirm", "gov_confirm") and text in ("تأیید", "تایید"):
        svc_key = "government" if step == "gov_confirm" else ("fida" if st.get("step_before") == "fida" else "print")
        rid, code = db.create_request(internal_id, svc_key, "rubika", int(st.get("amount", 0)))
        state.pop(uid, None)
        await message.reply(f"درخواست شما ثبت شد ✅\nکد پیگیری: {code}\n\nبرای پیگیری از گزینه 🎫 پیگیری استفاده کنید.")
        return
    if step == "partner_phone":
        await message.reply("پنل همکاران از این مسیر در نسخه فعلی مدیریت می‌شود.\n\n" + CANCEL); return
    await message.reply("یکی از گزینه‌های منو را انتخاب کنید.\n\n" + main_menu())

async def run():
    logging.info("NetYar Rubika bot starting...")
    await rubika.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())