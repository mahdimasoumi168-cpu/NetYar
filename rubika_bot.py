import os
import logging
import re
from rubka.asynco import Robot, Message
from core import db

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
TOKEN = os.getenv("RUBIKA_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("RUBIKA_BOT_TOKEN environment variable is missing.")

rubika = Robot(token=TOKEN, safeSendMode=True, max_cache_size=2000, max_msg_age=120)
state = {}

CANCEL = "❌ انصراف"

TEXT = {
    "fa": {
        "lang":"🌐 زبان را انتخاب کنید:\n1) فارسی\n2) English\n3) العربية",
        "cit":"آیا اتباع هستید یا ایرانی؟\n1) اتباع\n2) ایرانی",
        "iran":"🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.\n\n👥 پنل همکاران\n🎫 پیگیری",
        "menu":"خدمات موردنظر را انتخاب کنید:\n\n1) 🪪 فیدای غیر حضوری\n2) 🖨 خدمات چاپ\n3) 🏛 حل مشکل ورود اتباع سامانه دولت من\n4) 👥 پنل همکاران\n5) 🎫 پیگیری",
        "fida":"🪪 لطفاً تصویر مدرک شناسایی مشترک را ارسال کنید.",
        "print":"🖨 نوع چاپ را انتخاب کنید:\n1) سیاه و سفید\n2) رنگی",
        "side":"چاپ را انتخاب کنید:\n1) یک‌رو\n2) پشت‌ورو",
        "count":"تعداد نسخه موردنیاز از هر صفحه را وارد کنید.",
        "files":"📎 فایل‌ها یا عکس‌های موردنظر را ارسال کنید. پس از ارسال همه موارد، «تأیید» را بزنید.",
        "govf":"شناسه فیدای مشترک را وارد کنید.",
        "govy":"شناسه یکتای مشترک را وارد کنید.",
        "id":"🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.",
        "phone":"📱 شماره موبایل مشترک را وارد کنید. سیم‌کارت باید به نام خود مشترک باشد.",
        "dob":"🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.",
        "doc":"در صورت داشتن سند سیم‌کارت، تصویر آن را ارسال کنید؛ در غیر این صورت «ندارم» بنویسید.",
        "confirm":"برای ادامه «تأیید» و برای لغو «انصراف» را انتخاب کنید.",
        "track":"🎫 کد پیگیری را وارد کنید.",
        "notrack":"❌ کد پیگیری پیدا نشد.",
        "cancel":"عملیات لغو شد.\n\n",
        "bad":"لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.",
        "thanks":"درخواست شما ثبت شد ✅\nکد پیگیری: {code}\n\nبرای پیگیری، گزینه 🎫 پیگیری را انتخاب کنید.",
        "received":"✅ دریافت شد. اگر مورد دیگری دارید ارسال کنید؛ در پایان «تأیید» را بزنید.",
        "amount":"💳 هزینه خدمات: {amount:,} تومان\n\n{confirm}",
    },
    "en": {
        "lang":"🌐 Choose your language:\n1) فارسی\n2) English\n3) العربية",
        "cit":"Are you a foreign national or Iranian?\n1) Foreign national\n2) Iranian",
        "iran":"🇮🇷 Services are currently unavailable for Iranian users.\n\n👥 Partner Panel\n🎫 Track",
        "menu":"Please choose a service:\n\n1) 🪪 FIDA non‑in-person service\n2) 🖨 Printing service\n3) 🏛 Government My Services access issue\n4) 👥 Partner Panel\n5) 🎫 Track",
        "fida":"🪪 Please send the customer's identification document image.",
        "print":"🖨 Choose print type:\n1) Black & white\n2) Color",
        "side":"Choose printing mode:\n1) Single-sided\n2) Double-sided",
        "count":"Enter the number of copies required for each page.",
        "files":"📎 Send the required files/images. When finished, choose Confirm.",
        "govf":"Enter the customer's FIDA ID.",
        "govy":"Enter the customer's unique ID.",
        "id":"🪪 Please send the customer's identification document image.",
        "phone":"📱 Enter the customer's mobile number. The SIM must be registered to the customer.",
        "dob":"🎂 Enter the customer's birth date as 1356/01/01.",
        "doc":"If there is a SIM ownership document, send its image; otherwise type No.",
        "confirm":"Choose Confirm to continue or Cancel to stop.",
        "track":"🎫 Enter the tracking code.",
        "notrack":"❌ Tracking code not found.",
        "cancel":"Operation cancelled.\n\n",
        "bad":"Please choose one of the displayed options.",
        "thanks":"Your request was registered ✅\nTracking code: {code}\n\nChoose 🎫 Track to follow it.",
        "received":"✅ Received. Send another item if needed; choose Confirm when finished.",
        "amount":"💳 Service fee: {amount:,} toman\n\n{confirm}",
    },
    "ar": {
        "lang":"🌐 اختر اللغة:\n1) فارسی\n2) English\n3) العربية",
        "cit":"هل أنت من الرعايا الأجانب أم إيراني؟\n1) أجنبي\n2) إيراني",
        "iran":"🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين.\n\n👥 لوحة الشركاء\n🎫 متابعة",
        "menu":"اختر الخدمة المطلوبة:\n\n1) 🪪 خدمة فيدا عن بُعد\n2) 🖨 خدمة الطباعة\n3) 🏛 حل مشكلة الدخول إلى نظام خدمات الحكومة\n4) 👥 لوحة الشركاء\n5) 🎫 متابعة",
        "fida":"🪪 يرجى إرسال صورة وثيقة هوية العميل.",
        "print":"🖨 اختر نوع الطباعة:\n1) أبيض وأسود\n2) ملون",
        "side":"اختر طريقة الطباعة:\n1) وجه واحد\n2) وجهان",
        "count":"أدخل عدد النسخ المطلوبة لكل صفحة.",
        "files":"📎 أرسل الملفات أو الصور المطلوبة. عند الانتهاء اختر تأكيد.",
        "govf":"أدخل رقم فيدا الخاص بالعميل.",
        "govy":"أدخل المعرف الفريد الخاص بالعميل.",
        "id":"🪪 يرجى إرسال صورة وثيقة هوية العميل.",
        "phone":"📱 أدخل رقم هاتف العميل. يجب أن تكون الشريحة مسجلة باسم العميل.",
        "dob":"🎂 أدخل تاريخ ميلاد العميل بهذا الشكل 1356/01/01.",
        "doc":"إذا كان هناك مستند ملكية الشريحة فأرسل صورته، وإلا اكتب لا يوجد.",
        "confirm":"اختر تأكيد للمتابعة أو إلغاء للتوقف.",
        "track":"🎫 أدخل رمز المتابعة.",
        "notrack":"❌ لم يتم العثور على رمز المتابعة.",
        "cancel":"تم إلغاء العملية.\n\n",
        "bad":"يرجى اختيار أحد الخيارات المعروضة.",
        "thanks":"تم تسجيل طلبك ✅\nرمز المتابعة: {code}\n\nاختر 🎫 متابعة لمتابعة الطلب.",
        "received":"✅ تم الاستلام. أرسل عنصراً آخر إذا لزم؛ وعند الانتهاء اختر تأكيد.",
        "amount":"💳 تكلفة الخدمة: {amount:,} تومان\n\n{confirm}",
    },
}

def uid_of(message): return str(getattr(message, "sender_id", "") or "")
def name_of(message): return getattr(message, "first_name", None) or getattr(message, "username", None) or "کاربر"

def lang(uid):
    x = state.get(uid, {}).get("language", "fa")
    return x if x in TEXT else "fa"

def tr(uid, key, **kw):
    return TEXT[lang(uid)][key].format(**kw)

def is_cancel(t): return t.strip() in (CANCEL, "انصراف", "Cancel", "لغو", "إلغاء")
def is_confirm(t): return t.strip() in ("تأیید", "تایید", "Confirm", "تأكيد", "تأكيد")

async def show_language(message):
    state[uid_of(message)] = {"step":"language"}
    await message.reply(TEXT["fa"]["lang"])

def set_citizenship(st, value):
    st["citizenship"] = value
    st["step"] = "menu"

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

    if is_cancel(text):
        state.pop(uid, None)
        await message.reply(tr(uid, "cancel") + tr(uid, "menu")); return

    if db.setting("bot_open", "1") != "1":
        await message.reply("⏳ ربات موقتاً در حال بروزرسانی است."); return

    st = state.setdefault(uid, {"step":"language"})
    step = st.get("step")

    if step == "language":
        choices = {"1":"fa","فارسی":"fa","2":"en","English":"en","3":"ar","العربية":"ar"}
        if text not in choices:
            await message.reply(TEXT["fa"]["lang"]); return
        st["language"] = choices[text]
        st["step"] = "citizenship"
        await message.reply(tr(uid,"cit")); return

    if step == "citizenship":
        if text in ("2","ایرانی","Iranian","2) Iranian","إيراني","2) إيراني"):
            st["citizenship"]="iranian"; st["step"]="iranian_menu"
            await message.reply(tr(uid,"iran")); return
        if text in ("1","اتباع","Foreign national","أجنبي","1) Foreign national","1) أجنبي"):
            set_citizenship(st,"foreign")
            await message.reply(tr(uid,"menu")); return
        await message.reply(tr(uid,"bad")); return

    if step == "iranian_menu":
        if text in ("👥 پنل همکاران","🎫 پیگیری","Track","متابعة"):
            if "پیگیری" in text or text in ("Track","متابعة","🎫 پیگیری"):
                st["step"]="track"; await message.reply(tr(uid,"track")); return
            st["step"]="partner_phone"; await message.reply("📱 شماره همراه همکار را وارد کنید.\n\n"+CANCEL); return
        await message.reply(tr(uid,"iran")); return

    if text in ("5","🎫 پیگیری","پیگیری","Track","متابعة"):
        st["step"]="track"; await message.reply(tr(uid,"track")); return

    if step == "track":
        r = db.conn.execute("SELECT * FROM requests WHERE tracking_code=?", (text,)).fetchone()
        if r: await message.reply(tr(uid,"thanks",code=text).replace(tr(uid,"thanks",code=text).split("\n")[0],"🎫 وضعیت درخواست شما"))
        else: await message.reply(tr(uid,"notrack"))
        state.pop(uid, None); return

    if step == "menu":
        if text in ("1","🪪 فیدای غیر حضوری","FIDA non‑in-person service","خدمة فيدا عن بُعد"):
            st["step"]="fida_id"; await message.reply(tr(uid,"fida")); return
        if text in ("2","🖨 خدمات چاپ","Printing service","خدمة الطباعة"):
            st["step"]="print_color"; await message.reply(tr(uid,"print")); return
        if text in ("3","🪪 حل مشکل ورود اتباع سامانه دولت من","Government My Services access issue","حل مشكلة الدخول إلى نظام خدمات الحكومة"):
            st["step"]="gov_fida"; await message.reply(tr(uid,"govf")); return
        if text in ("4","👥 پنل همکاران","Partner Panel","لوحة الشركاء"):
            st["step"]="partner_phone"; await message.reply("📱 شماره همراه همکار را وارد کنید.\n\n"+CANCEL); return
        await message.reply(tr(uid,"menu")); return

    if step == "track":
        return

    if step == "gov_fida":
        st["fida"]=text; st["step"]="gov_yekta"; await message.reply(tr(uid,"govy")); return
    if step == "gov_yekta":
        st["yekta"]=text; st["step"]="gov_id"; await message.reply(tr(uid,"id")); return
    if step == "gov_id":
        st["step"]="gov_sim"; await message.reply(tr(uid,"phone")); return
    if step == "gov_sim":
        st["phone"]=text; st["step"]="gov_dob"; await message.reply(tr(uid,"dob")); return
    if step == "gov_dob":
        if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])", text):
            await message.reply("❌ "+tr(uid,"dob")); return
        st["dob"]=text; st["step"]="gov_carddoc"; await message.reply(tr(uid,"doc")); return
    if step == "gov_carddoc":
        svc=db.service("government"); amount=int(svc["price"] if svc else 500000)
        st["step"]="gov_confirm"; st["amount"]=amount
        await message.reply(tr(uid,"amount",amount=amount)); return

    if step == "print_color":
        if text in ("1","سیاه و سفید","Black & white","أبيض وأسود"): st["color"]="bw"
        elif text in ("2","رنگی","Color","ملون"): st["color"]="color"
        else: await message.reply(tr(uid,"print")); return
        st["step"]="print_side"; await message.reply(tr(uid,"side")); return
    if step == "print_side":
        if text in ("1","یک‌رو","Single-sided","وجه واحد"): st["side"]="single"
        elif text in ("2","پشت‌ورو","Double-sided","وجهان"): st["side"]="double"
        else: await message.reply(tr(uid,"side")); return
        st["step"]="print_count"; await message.reply(tr(uid,"count")); return
    if step == "print_count":
        if not text.isdigit() or int(text)<1: await message.reply(tr(uid,"count")); return
        st["count"]=int(text); st["step"]="print_files"; st["files"]=[]; await message.reply(tr(uid,"files")); return

    if step == "print_files":
        if is_confirm(text):
            svc=db.service("print"); amount=int(svc["price"] if svc else 0)
            st["step"]="print_confirm"; st["amount"]=amount
            await message.reply(tr(uid,"amount",amount=amount)); return
        st.setdefault("files",[]).append(text)
        await message.reply(tr(uid,"received")); return

    if step == "fida_id":
        if is_confirm(text):
            svc=db.service("fida"); amount=int(svc["price"] if svc else 0)
            st["step"]="fida_confirm"; st["amount"]=amount
            await message.reply(tr(uid,"amount",amount=amount)); return
        st["fida_document"]=text; await message.reply(tr(uid,"received")); return

    if step in ("fida_confirm","print_confirm","gov_confirm"):
        if is_confirm(text):
            svc_key="government" if step=="gov_confirm" else ("print" if step=="print_confirm" else "fida")
            rid,code=db.create_request(internal_id,svc_key,"rubika",int(st.get("amount",0)))
            state.pop(uid,None)
            await message.reply(tr(uid,"thanks",code=code)); return
        await message.reply(tr(uid,"confirm")); return

    if step == "partner_phone":
        await message.reply("پنل همکاران از مسیر اختصاصی همکاران مدیریت می‌شود.\n\n"+CANCEL); return

    await message.reply(tr(uid,"menu"))

async def run():
    logging.info("NetYar Rubika bot starting...")
    await rubika.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
