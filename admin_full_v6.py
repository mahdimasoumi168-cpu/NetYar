"""Full Telegram admin panel v6: management, services, reports, announcements and bot registry."""
import asyncio, logging, os
import bot as B
from core import db, now

log = logging.getLogger("netyar.admin_full_v6")

MENU = [
    ["👤 کاربران", "👥 همکاران"],
    ["➕ افزودن همکار", "💰 شارژها"],
    ["📋 درخواست‌ها", "⚙️ قیمت‌ها"],
    ["🟢 خدمات", "📊 گزارش کامل"],
    ["📣 اعلان همگانی", "🤖 بات‌های متصل"],
    ["➕ افزودن بات", "🧾 لاگ مدیریت"],
    ["⚙️ تنظیمات سیستم", "⬅️ منوی اصلی"],
]

def amenu():
    return B.kb(MENU)

async def _send_announcement(app, text):
    rows = db.conn.execute("SELECT external_id FROM users WHERE platform='telegram'").fetchall()
    ok = fail = 0
    for r in rows:
        try:
            await app.bot.send_message(chat_id=int(r["external_id"]), text=text)
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    return ok, fail

async def admin_text(u, c):
    uid = u.effective_user.id
    if not B.admin(uid):
        return
    t = (u.message.text or "").strip()
    st = B.S.setdefault(uid, {"admin": True})
    st["admin"] = True

    if st.get("mode") == "admin_add_partner":
        if t in (B.CANCEL, "لغو", "انصراف"):
            st["mode"] = None; return await u.message.reply_text("لغو شد.", reply_markup=amenu())
        parts = [x.strip() for x in t.split("|")]
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
            return await u.message.reply_text("فرمت صحیح:\nشماره | رمز | نام همکار", reply_markup=B.cancel_kb())
        try:
            B.db.add_partner(parts[0], parts[1], parts[2])
            st["mode"] = None
            return await u.message.reply_text("✅ همکار با موفقیت اضافه شد.", reply_markup=amenu())
        except Exception as e:
            log.exception("add partner")
            return await u.message.reply_text("❌ ثبت نشد؛ شماره احتمالاً تکراری است.", reply_markup=amenu())

    if st.get("mode") == "admin_price":
        if t in (B.CANCEL, "لغو", "انصراف"):
            st["mode"] = None; return await u.message.reply_text("لغو شد.", reply_markup=amenu())
        parts = t.replace("تومان", "").replace(" ", "").split("=")
        if len(parts) != 2 or not parts[0] or not parts[1].isdigit():
            return await u.message.reply_text("فرمت صحیح: government=500000", reply_markup=B.cancel_kb())
        db.set_setting("price_" + parts[0], int(parts[1]))
        st["mode"] = None
        return await u.message.reply_text(f"✅ قیمت {parts[0]} روی {int(parts[1]):,} تومان تنظیم شد.", reply_markup=amenu())

    if st.get("mode") == "admin_announce":
        if t in (B.CANCEL, "لغو", "انصراف"):
            st["mode"] = None; return await u.message.reply_text("لغو شد.", reply_markup=amenu())
        st["mode"] = None
        ok, fail = await _send_announcement(c.application, t)
        db.audit("telegram", uid, "announcement", "users", t[:500])
        return await u.message.reply_text(f"📣 اعلان ارسال شد.\n✅ موفق: {ok}\n❌ ناموفق: {fail}", reply_markup=amenu())

    if st.get("mode") == "admin_add_bot":
        parts = [x.strip() for x in t.split("|")]
        if len(parts) != 3:
            return await u.message.reply_text("فرمت صحیح:\nplatform | bot name | API\nمثال: bale | کمک یار | API", reply_markup=B.cancel_kb())
        platform, name, api = parts
        if platform.lower() not in {"telegram", "rubika", "bale", "eitaa"}:
            return await u.message.reply_text("❌ پیام‌رسان باید telegram / rubika / bale / eitaa باشد.", reply_markup=B.cancel_kb())
        # Store only a masked reference; never echo the secret API in the panel.
        ref = "configured:" + api[:4] + "…" if api else "configured"
        db.add_bot(platform.lower(), name, ref)
        st["mode"] = None
        return await u.message.reply_text("✅ بات ثبت شد.\n⚠️ فعال‌سازی اجرایی پیام‌رسان‌های جدید نیازمند اتصال runtime همان پیام‌رسان است.", reply_markup=amenu())

    if t == "👤 کاربران":
        rows = db.conn.execute("SELECT id,platform,external_id,username,full_name,created_at FROM users ORDER BY id DESC LIMIT 100").fetchall()
        text = "👤 کاربران\n\n" + ("\n".join(f"#{r['id']} | {r['platform']} | {r['full_name'] or '-'} | @{r['username'] or '-'} | {r['created_at'] or '-'}" for r in rows) or "کاربری ثبت نشده است.")
        return await u.message.reply_text(text[:3900], reply_markup=amenu())

    if t == "👥 همکاران":
        rows = db.conn.execute("SELECT id,name,phone,balance,active,created_at FROM partners ORDER BY id DESC").fetchall()
        text = "👥 همکاران\n\n" + ("\n".join(f"#{r['id']} | {r['name']} | {r['phone']} | 💰 {r['balance']:,} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rows) or "همکاری ثبت نشده است.")
        return await u.message.reply_text(text[:3900], reply_markup=amenu())

    if t == "➕ افزودن همکار":
        st["mode"] = "admin_add_partner"
        return await u.message.reply_text("➕ افزودن همکار\n\nفرمت:\nشماره | رمز | نام همکار\nمثال: 09xxxxxxxxx | رمز جدید | همکار اصفهان", reply_markup=B.cancel_kb())

    if t == "💰 شارژها":
        rows = db.conn.execute("SELECT id,partner_id,amount,status,created_at,reviewed_at FROM topups ORDER BY id DESC LIMIT 50").fetchall()
        lines=[]
        for r in rows:
            p=db.conn.execute("SELECT name FROM partners WHERE id=?",(r['partner_id'],)).fetchone()
            lines.append(f"#{r['id']} | {p['name'] if p else '-'} | {r['amount']:,} | {r['status']} | {r['created_at']}")
        return await u.message.reply_text("💰 شارژها\n\n"+("\n".join(lines) or "موردی نیست."), reply_markup=amenu())

    if t == "📋 درخواست‌ها":
        rows=db.conn.execute("SELECT id,tracking_code,service_key,platform,status,amount,payment_status,created_at FROM requests ORDER BY id DESC LIMIT 50").fetchall()
        if not rows:return await u.message.reply_text("📋 درخواستی ثبت نشده است.",reply_markup=amenu())
        text="📋 درخواست‌ها\n\n"+"\n".join(f"#{r['id']} | {r['tracking_code']} | {r['service_key']} | {r['platform']} | {r['status']} | {r['amount']:,}" for r in rows)
        return await u.message.reply_text(text[:3900],reply_markup=amenu())

    if t == "⚙️ قیمت‌ها":
        rows=db.conn.execute("SELECT key,value FROM settings WHERE key LIKE 'price_%' ORDER BY key").fetchall()
        text="⚙️ قیمت خدمات\n\n"+"\n".join(f"{r['key'][6:]} = {r['value']:,} تومان" for r in rows)
        st["mode"]="admin_price"
        return await u.message.reply_text(text+"\n\nبرای تغییر: key=amount",reply_markup=B.cancel_kb())

    if t == "🟢 خدمات":
        rows=db.conn.execute("SELECT key,name,description,price,active FROM services ORDER BY id").fetchall()
        text="🟢 خدمات\n\n"+"\n".join(f"{r['key']} | {r['name']} | {r['price']:,} | {'فعال' if r['active'] else 'خاموش'}\n{r['description']}" for r in rows)
        return await u.message.reply_text(text or "خدمتی ثبت نشده است.",reply_markup=amenu())

    if t == "📊 گزارش کامل":
        users=db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        partners=db.conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0]
        req=db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        pending=db.conn.execute("SELECT COUNT(*) FROM requests WHERE status IN ('new','submitted','awaiting_payment')").fetchone()[0]
        topup=db.conn.execute("SELECT COALESCE(SUM(amount),0) FROM topups WHERE status='approved'").fetchone()[0]
        revenue=db.conn.execute("SELECT COALESCE(SUM(amount),0) FROM requests WHERE payment_status='paid'").fetchone()[0]
        return await u.message.reply_text(f"📊 گزارش کامل\n\n👤 کاربران: {users}\n👥 همکاران: {partners}\n📋 کل درخواست‌ها: {req}\n⏳ در انتظار: {pending}\n💰 شارژ تأییدشده: {topup:,} تومان\n💳 مبالغ پرداخت‌شده: {revenue:,} تومان",reply_markup=amenu())

    if t == "📣 اعلان همگانی":
        st["mode"]="admin_announce"
        return await u.message.reply_text("📣 متن اعلان را ارسال کنید. برای لغو «انصراف» بفرستید.",reply_markup=B.cancel_kb())

    if t == "🤖 بات‌های متصل":
        rows=db.bots()
        text="🤖 بات‌های ثبت‌شده\n\n"+("\n".join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) or "هنوز باتی ثبت نشده است.")
        return await u.message.reply_text(text,reply_markup=amenu())

    if t == "➕ افزودن بات":
        st["mode"]="admin_add_bot"
        return await u.message.reply_text("➕ افزودن بات\n\nفرمت:\nplatform | bot name | API\n\nپشتیبانی مدیریتی: telegram / rubika / bale / eitaa",reply_markup=B.cancel_kb())

    if t == "🧾 لاگ مدیریت":
        rows=db.conn.execute("SELECT platform,actor_id,action,target,details,created_at FROM audit_log ORDER BY id DESC LIMIT 50").fetchall()
        text="🧾 لاگ مدیریت\n\n"+"\n".join(f"{r['created_at']} | {r['platform']} | {r['action']} | {r['target']} | {r['details'][:80]}" for r in rows)
        return await u.message.reply_text(text[:3900] or "لاگی ثبت نشده است.",reply_markup=amenu())

    if t == "⚙️ تنظیمات سیستم":
        rows=db.conn.execute("SELECT key,value FROM settings ORDER BY key").fetchall()
        text="⚙️ تنظیمات سیستم\n\n"+"\n".join(f"{r['key']} = {r['value']}" for r in rows)
        return await u.message.reply_text(text[:3900],reply_markup=amenu())

    if t == "⬅️ منوی اصلی":
        st["mode"] = None
        return await u.message.reply_text("منوی اصلی",reply_markup=B.main(uid))

    return await u.message.reply_text("گزینه مدیریت شناخته نشد.",reply_markup=amenu())


def install():
    B.amenu = amenu
    B.admin_text = admin_text
    log.info("Full Telegram admin panel v6 installed")
