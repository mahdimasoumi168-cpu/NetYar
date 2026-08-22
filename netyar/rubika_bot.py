import os
import logging
from types import SimpleNamespace

from rubka.asynco import Robot, Message

# Reuse NetYar's database/settings/service logic so Telegram and Rubika share one backend.
from bot import (
    db, init_db, setting, button, bot_open, is_admin, ADMIN_IDS,
    now, upsert_user
)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
TOKEN = os.getenv("RUBIKA_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("RUBIKA_BOT_TOKEN environment variable is missing.")

rubika = Robot(
    token=TOKEN,
    safeSendMode=True,
    max_cache_size=2000,
    max_msg_age=120,
)

# Per-Rubika-user state for multi-step service requests.
state = {}


def user_name(message):
    return getattr(message, "first_name", None) or getattr(message, "username", None) or "کاربر روبیکا"


def rubika_user_id(message):
    return str(getattr(message, "sender_id", ""))


def rubika_chat_id(message):
    return str(getattr(message, "chat_id", ""))


def main_text():
    labels = [button(k)[0] for k in ("register", "services", "track", "announcements", "support", "about") if button(k)[1]]
    return "\n".join("• " + x for x in labels)


async def send_main(message, extra=""):
    text = setting("welcome").replace("\\n", "\n")
    text += "\n\n" + main_text()
    if extra:
        text += "\n\n" + extra
    await message.reply(text)


@rubika.on_message(commands=["start"])
async def start(_: Robot, message: Message):
    uid = rubika_user_id(message)
    if not uid:
        return
    internal_id = upsert_user(SimpleNamespace(id=uid, username="", full_name=user_name(message)), platform="rubika", external_id=uid)
    if not bot_open() and not is_admin(internal_id):
        await message.reply(setting("maintenance"))
        return
    await send_main(message)


@rubika.on_message()
async def all_messages(_: Robot, message: Message):
    uid = rubika_user_id(message)
    chat_id = rubika_chat_id(message)
    if not uid or not chat_id:
        return
    text = (getattr(message, "text", "") or "").strip()
    internal_id = upsert_user(SimpleNamespace(id=uid, username="", full_name=user_name(message)), platform="rubika", external_id=uid)

    if text in ("/start", "شروع"):
        await send_main(message)
        return

    if not bot_open() and not is_admin(internal_id):
        await message.reply(setting("maintenance"))
        return

    # Continue a service request.
    if uid in state:
        await handle_service_answer(message, internal_id)
        return

    labels = {k: button(k)[0] for k in ("services", "announcements", "support", "about", "track")}
    if text == labels["services"] or text in ("🏢 خدمات دفتر", "خدمات"):
        await services_menu(message, internal_id)
    elif text == labels["announcements"] or text == "📢 اطلاعیه‌ها":
        await message.reply(setting("announcements"))
    elif text == labels["support"] or text == "☎️ پشتیبانی":
        await message.reply(setting("support"))
    elif text == labels["about"] or text == "ℹ️ درباره ما":
        await message.reply(setting("about"))
    elif text == labels["track"] or text == "🔎 پیگیری درخواست":
        await message.reply("شماره درخواست را ارسال کنید.")
    elif text in ("📝 ثبت نام", "ثبت نام"):
        await message.reply("ثبت‌نام روبیکا در این نسخه به صورت پایه فعال است؛ شماره موبایل، کد شناسایی و شهر را می‌توانیم در مرحله بعد اضافه کنیم.")
    elif text in ("🛠 پنل مدیریت", "/admin"):
        if is_admin(internal_id):
            await message.reply("🔐 شما مدیر روبیکا هستید. پنل اصلی مدیریت همچنان از ربات تلگرام قابل استفاده است.")
        else:
            await message.reply("⛔ دسترسی ندارید.")
    else:
        await send_main(message, "پیام شما دریافت شد. یکی از گزینه‌های بالا را انتخاب کنید.")


async def services_menu(message, internal_id):
    rows = db.execute("SELECT * FROM services WHERE active=1 ORDER BY id").fetchall()
    if not rows:
        await message.reply("هنوز خدمتی تعریف نشده است.")
        return
    # Simple text menu is intentionally used first for maximum compatibility with Rubika versions.
    state.setdefault("_services", {})
    state["_services"][rubika_user_id(message)] = {"internal_id": internal_id, "services": {str(r["id"]): dict(r) for r in rows}}
    lines = ["🏢 خدمات دفتر:\n"]
    for r in rows:
        price = r["price"] or "اعلام نشده"
        lines.append(f"{r['id']}) {r['name']} — {price}")
    lines.append("\nشماره خدمت را ارسال کنید.")
    await message.reply("\n".join(lines))


async def handle_service_answer(message, internal_id):
    uid = rubika_user_id(message)
    # Selecting a service from the service list.
    svc_store = state.get("_services", {}).get(uid)
    if svc_store and uid not in state:
        return
    if uid not in state:
        if svc_store and (getattr(message, "text", "") or "").strip().isdigit():
            sid = (getattr(message, "text", "") or "").strip()
            if sid in svc_store["services"]:
                s = svc_store["services"][sid]
                steps = db.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no", (int(sid),)).fetchall()
                if not steps:
                    await message.reply(f"🏢 {s['name']}\n{s['description']}\n💰 {s['price'] or 'اعلام نشده'}\n\nاین خدمت هنوز مرحله‌ای ندارد.")
                    return
                cur = db.execute("INSERT INTO requests(user_id,service_id,status,created_at,updated_at) VALUES(?,?,?,?,?)", (internal_id, int(sid), "new", now(), now()))
                rid = cur.lastrowid
                db.commit()
                state[uid] = {"request_id": rid, "steps": [dict(x) for x in steps], "index": 0, "internal_id": internal_id}
                state["_services"].pop(uid, None)
                await message.reply(f"درخواست #{rid} ثبت شد.\n\n{steps[0]['prompt']}")
            return
        return

    ctx = state[uid]
    idx = ctx["index"]
    steps = ctx["steps"]
    st = steps[idx]
    answer = getattr(message, "text", "") or ""
    db.execute("INSERT INTO request_answers(request_id,step_id,answer,file_id,created_at) VALUES(?,?,?,?,?)", (ctx["request_id"], st["id"], answer, "", now()))
    idx += 1
    ctx["index"] = idx
    if idx < len(steps):
        db.commit()
        await message.reply(steps[idx]["prompt"])
        return
    db.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (now(), ctx["request_id"]))
    db.commit()
    rid = ctx["request_id"]
    state.pop(uid, None)
    await message.reply(f"درخواست #{rid} کامل ثبت شد ✅")
    logging.info("Rubika request submitted: %s", rid)


async def run():
    init_db()
    logging.info("NetYar Rubika bot starting...")
    await rubika.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
