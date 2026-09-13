"""Single fail-safe Telegram callback router.

This module is deliberately independent from the legacy callback wrappers.
It receives an already-resolved ui2 label and executes the real action directly.
"""
from types import SimpleNamespace
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop


def _fake(update, label):
    q = update.callback_query
    original = q.message
    class MessageProxy:
        def __init__(self, msg, text):
            self._msg = msg
            self.text = str(text or "")
        def __getattr__(self, name):
            return getattr(self._msg, name)
    msg = MessageProxy(original, label)
    return SimpleNamespace(
        update_id=getattr(update, "update_id", None),
        message=msg,
        effective_message=msg,
        effective_user=update.effective_user,
        effective_chat=getattr(original, "chat", None),
        callback_query=q,
    )


def _admin_menu(B):
    try:
        import telegram_admin_plus as A
        return A._admin_menu()
    except Exception:
        try:
            return B.amenu()
        except Exception:
            return None


async def handle(update, context, B, label):
    q = update.callback_query
    if not q or not q.message:
        return
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})
    label = str(label or "").strip()
    fake = _fake(update, label)

    if label in {"🔄 شروع مجدد", "🔄 شروع دوباره", "Restart", "Start again"}:
        old = dict(st)
        B.S[uid] = {"lang": old.get("lang", "fa")}
        status = old.get("status") or old.get("citizenship")
        if status:
            B.S[uid].update(status=status, citizenship=status)
        return await B.start(fake, context)

    if label in {"❌ انصراف", "❌ Cancel", "❌ إلغاء"}:
        return await B.cancel(fake, context)

    if label in {"👥 پنل همکاران", "👥 Partner panel", "👥 لوحة الشركاء"}:
        if st.get("partner_logged_out"):
            st.pop("partner_id", None)
            st.pop("partner_active", None)
        pid = st.get("partner_id")
        if pid and st.get("partner_active", True):
            row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            if row:
                st["partner_active"] = True
                st["partner_logged_out"] = False
                st["mode"] = None
                return await q.message.reply_text(
                    f"👥 پنل همکاران\n👤 {row['name'] or '-'}\n📱 {row['phone'] or '-'}\n💰 اعتبار: {int(row['balance'] or 0):,} تومان",
                    reply_markup=B.partner_kb(st.get("lang", "fa")),
                )
        st["mode"] = "p_phone"
        st.pop("phone", None)
        st.pop("partner_active", None)
        return await q.message.reply_text(
            "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    if label in {"🛠 پنل مدیریت بات", "🛠 Admin panel", "🛠 لوحة الإدارة"}:
        if not B.admin(uid):
            return await q.message.reply_text("❌ دسترسی مدیریت ندارید.", reply_markup=B.main(uid))
        return await q.message.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:", reply_markup=_admin_menu(B))

    routes = {
        "➕ شارژ حساب": "topup",
        "🏛 حل مشکل سامانه دولت من": "gov",
        "🔎 پیگیری کد": "ptrack",
        "📋 سوابق": "phistory",
        "🪪 فیدای غیر حضوری": "fida",
        "🖨 خدمات چاپ": "prt",
        "🪪 حل مشکل ورود اتباع دولت من": "gov",
    }
    if label in routes:
        fn = getattr(B, routes[label], None)
        if fn:
            return await fn(fake, context)
        return await q.message.reply_text("❌ این خدمت فعلاً در دسترس نیست.", reply_markup=B.main(uid))

    if label == "💰 موجودی":
        pid = st.get("partner_id")
        if pid:
            row = B.db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
            balance = int(row["balance"] or 0) if row else 0
            return await q.message.reply_text(f"💰 اعتبار فعلی شما: {balance:,} تومان", reply_markup=B.partner_kb(st.get("lang", "fa")))
        fn = getattr(B, "customer_wallet", None)
        if fn:
            return await fn(fake, context)
        return await q.message.reply_text("💰 کیف پول من\n\nموجودی کیف پول شما فعلاً صفر است.", reply_markup=B.main(uid))

    if label in {"🎫 تیکت به مدیریت", "✉️ تیکت به مدیریت", "✉️ Ticket to admin", "🎫 Ticket to admin"}:
        try:
            from telegram_business_features import _send_ticket_prompt
            return await _send_ticket_prompt(fake, B)
        except Exception:
            st["mode"] = "partner_message"
            return await q.message.reply_text("✉️ لطفاً پیام خود را برای مدیریت ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))

    if label == "📱 خدمات سیم کارت":
        fn = getattr(B, "sim_start", None)
        if fn:
            return await fn(fake, context)
        return await q.message.reply_text("❌ خدمات سیم کارت فعلاً در دسترس نیست.", reply_markup=B.main(uid))

    if label == "🎫 پیگیری":
        st["mode"] = "public_tracking"
        return await q.message.reply_text("🎫 کد پیگیری را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))

    if label == "💰 کیف پول من":
        fn = getattr(B, "customer_wallet", None)
        if fn:
            return await fn(fake, context)
        return await q.message.reply_text("💰 کیف پول من\n\nموجودی کیف پول شما فعلاً صفر است.", reply_markup=B.main(uid))

    if label == "📞 تماس با ما":
        return await q.message.reply_text("📞 تماس با ما\n\nبرای ارتباط با پشتیبانی روی دکمه زیر بزنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 ارتباط با پشتیبانی", url="https://t.me/Good_ok_2000")]]))

    if label == "📝 ثبت شکایت مشتریان":
        st["mode"] = "ui2_complaint"
        return await q.message.reply_text("📝 ثبت شکایت مشتریان\n\nمتن شکایت یا انتقاد خود را ارسال کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))

    # Final compatibility path for labels emitted by older service modules.
    result = await B.router(fake, context)
    if result is not None:
        return result
    return await q.message.reply_text("❌ این گزینه فعلاً در دسترس نیست.", reply_markup=B.main(uid))
