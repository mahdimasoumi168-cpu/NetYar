import os
import logging
from types import SimpleNamespace

from rubka.asynco import Robot, Message

# Reuse NetYar's database/settings/service logic so Telegram and Rubika share one backend.
from core import db, now

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


def is_admin(internal_id):
    """Check if a user is admin by looking up their Rubika external ID in admins table."""
    from core import db
    # internal_id is the database user.id, but we need platform+external_id to check admins table.
    # For now, query users to get the Rubika external_id.
    user = db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='rubika'", (internal_id,)).fetchone()
    if not user:
        return False
    external_id = user["external_id"]
    admin = db.conn.execute("SELECT * FROM admins WHERE platform='rubika' AND external_id=? AND active=1", (external_id,)).fetchone()
    return admin is not None


def main_text():
    """Build main menu text from available features."""
    # Simple hardcoded menu for Rubika; customize as needed
    labels = [
        "🏢 خدمات دفتر",
        "📢 اطلاعیه‌ها", 
        "🔎 پیگیری درخواست",
        "☎️ پشتیبانی",
        "ℹ️ درباره ما"
    ]
    return "\n".join("• " + x for x in labels)


async def send_main(message, extra=""):
    text = db.setting("welcome_fa", "سلام و خوش آمدید 🌷").replace("\\n", "\n")
    text += "\n\n" + main_text()
    if extra:
        text += "\n\n" + extra
    await message.reply(text)


@rubika.on_message(commands=["start"])
async def start(_: Robot, message: Message):
    uid = rubika_user_id(message)
    if not uid:
        return
    internal_id = db.user("rubika", uid, "", user_name(message))
    if db.setting("bot_open", "1") != "1":
        await message.reply("⏳ ربات موقتاً در حال بروزرسانی است.")
        return
    await send_main(message)


@rubika.on_message()
async def all_messages(_: Robot, message: Message):
    uid = rubika_user_id(message)
    chat_id = rubika_chat_id(message)
    if not uid or not chat_id:
        return
    text = (getattr(message, "text", "") or "").strip()
    internal_id = db.user("rubika", uid, "", user_name(message))

    if text in ("/start", "شروع"):
        await send_main(message)
        return

    if db.setting("bot_open", "1") != "1":
        await message.reply("⏳ ربات موقتاً در حال بروزرسانی است.")
        return

    # Continue a service request.
    if uid in state:
        await handle_service_answer(message, internal_id)
        return

    if text == "🏢 خدمات دفتر" or text in ("خدمات", "🏢 خدمات"):
        await services_menu(message, internal_id)
    elif text == "📢 اطلاعیه‌ها":
        await message.reply(db.setting("announcements", "اطلاعیه‌ای موجود نیست."))
    elif text == "☎️ پشتیبانی":
        await message.reply(db.setting("support", "با ما تماس بگیرید."))
    elif text == "ℹ️ درباره ما":
        await message.reply(db.setting("about", "درباره ما اطلاعاتی موجود نیست."))
    elif text == "🔎 پیگیری درخواست":
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
    """Display available services."""
    rows = db.conn.execute("SELECT * FROM services WHERE active=1 ORDER BY id").fetchall()
    if not rows:
        await message.reply("هنوز خدمتی تعریف نشده است.")
        return
    # Simple text menu for maximum compatibility with Rubika versions.
    state.setdefault("_services", {})
    state["_services"][rubika_user_id(message)] = {"internal_id": internal_id, "services": {str(r["id"]): dict(r) for r in rows}}
    lines = ["🏢 خدمات دفتر:\n"]
    for r in rows:
        price = r["price"] or "اعلام نشده"
        lines.append(f"{r['id']}) {r['name']} — {price}")
    lines.append("\nشماره خدمت را ارسال کنید.")
    await message.reply("\n".join(lines))


async def handle_service_answer(message, internal_id):
    """Handle user responses in multi-step service request flow."""
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
                steps = db.conn.execute("SELECT * FROM services WHERE active=1 AND id=? ORDER BY id", (int(sid),)).fetchall()
                if not steps:
                    await message.reply(f"🏢 {s['name']}\n{s['description']}\n💰 {s['price'] or 'اعلام نشده'}\n\nاین خدمت هنوز مرحله‌ای ندارد.")
                    return
                cur = db.conn.execute("INSERT INTO requests(user_id,service_id,status,created_at,updated_at) VALUES(?,?,?,?,?)", (internal_id, int(sid), "new", now(), now()))
                rid = cur.lastrowid
                db.conn.commit()
                state[uid] = {"request_id": rid, "steps": [dict(x) for x in steps], "index": 0, "internal_id": internal_id}
                state["_services"].pop(uid, None)
                await message.reply(f"درخواست #{rid} ثبت شد.")
            return
        return

    ctx = state[uid]
    idx = ctx["index"]
    steps = ctx["steps"]
    st = steps[idx] if idx < len(steps) else None
    if not st:
        return
    answer = getattr(message, "text", "") or ""
    db.conn.execute("INSERT INTO request_answers(request_id,step_id,answer,file_id,created_at) VALUES(?,?,?,?,?)", (ctx["request_id"], st["id"], answer, "", now()))
    idx += 1
    ctx["index"] = idx
    if idx < len(steps):
        db.conn.commit()
        await message.reply("سوال بعدی:")
        return
    db.conn.execute("UPDATE requests SET status='submitted',updated_at=? WHERE id=?", (now(), ctx["request_id"]))
    db.conn.commit()
    rid = ctx["request_id"]
    state.pop(uid, None)
    await message.reply(f"درخواست #{rid} کامل ثبت شد ✅")
    logging.info("Rubika request submitted: %s", rid)


async def run():
    logging.info("NetYar Rubika bot starting...")
    await rubika.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())

