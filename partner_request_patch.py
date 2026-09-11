"""Partner request receipt/ticket UX and Rubika->Telegram admin bridge.

Adds a confirmation message to partners after a request is created, with
edit/restart and ticket-to-admin actions. Also mirrors Rubika requests to the
Telegram admins configured in ADMIN_IDS using TELEGRAM_BOT_TOKEN.
"""
import os
import re
import logging
import requests

log = logging.getLogger("netyar.partner_request")


def _last_request(db, owner, after_id=0):
    try:
        return db.conn.execute(
            "SELECT * FROM requests WHERE user_id=? AND id>? ORDER BY id DESC LIMIT 1",
            (owner, int(after_id)),
        ).fetchone()
    except Exception:
        return None


def _service_name(key):
    return {
        "fida": "🪪 فیدای غیر حضوری",
        "print": "🖨 خدمات چاپ",
        "government": "🏛 حل مشکل ورود اتباع دولت من",
    }.get(str(key), str(key or "خدمت"))


def _telegram_admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    return [x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip() and x.strip().isdigit()]


def _mirror_rubika_to_telegram(text, request_row=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or os.getenv("BOT_TOKEN", "").strip()
    admins = _telegram_admin_ids()
    if not token or not admins:
        log.warning("Rubika->Telegram bridge skipped: Telegram token/admin ids are not configured")
        return
    payload_text = "📥 درخواست جدید از روبیکا\n\n" + str(text)
    if request_row:
        payload_text += f"\n\n🆔 شناسه داخلی درخواست: {request_row['id']}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for aid in admins:
        try:
            r = requests.post(url, json={"chat_id": int(aid), "text": payload_text}, timeout=15)
            r.raise_for_status()
        except Exception:
            log.exception("failed to mirror Rubika request to Telegram admin %s", aid)


def install():
    import bot as B
    import telegram_runtime as TG

    if getattr(B, "_partner_request_patch_installed", False):
        return

    old_router = B.router
    async def router(update, context):
        uid = int(update.effective_user.id)
        st = B.S.setdefault(uid, {})
        partner_id = st.get("partner_id")
        before = 0
        if partner_id:
            try:
                row = B.db.conn.execute("SELECT COALESCE(MAX(id),0) AS m FROM requests WHERE user_id=?", (partner_id,)).fetchone()
                before = int(row["m"] or 0)
            except Exception:
                pass
        result = await old_router(update, context)
        if partner_id:
            row = _last_request(B.db, partner_id, before)
            if row:
                text = (
                    "📋 درخواست شما ثبت شد.\n\n"
                    f"🛠 خدمت: {_service_name(row['service_key'])}\n"
                    f"🎫 کد پیگیری: {row['tracking_code']}\n"
                    f"💰 مبلغ: {int(row['amount'] or 0):,} تومان\n"
                    f"📌 وضعیت: {row['status']}\n\n"
                    "از گزینه‌های زیر استفاده کنید:"
                )
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ ویرایش درخواست", callback_data=f"pr:self:edit:{row['id']}")],
                    [InlineKeyboardButton("✉️ ارسال تیکت به مدیریت بات", callback_data=f"pr:self:ticket:{row['id']}")],
                ])
                try:
                    await update.effective_chat.send_message(text=text, reply_markup=markup)
                except Exception:
                    log.exception("failed to send partner request receipt")
        return result
    B.router = router

    async def partner_request_callback(update, context):
        q = update.callback_query
        await q.answer()
        parts = str(q.data or "").split(":")
        if len(parts) != 4:
            return
        try:
            rid = int(parts[3])
        except ValueError:
            return
        row = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        if not row:
            return await q.message.reply_text("❌ درخواست پیدا نشد.")
        uid = int(q.from_user.id)
        st = B.S.setdefault(uid, {})
        if int(st.get("partner_id") or -1) != int(row["user_id"]):
            return await q.message.reply_text("❌ این درخواست متعلق به شما نیست.")
        if parts[2] == "ticket":
            text = (
                "✉️ تیکت همکار\n"
                f"🎫 {row['tracking_code']}\n"
                f"🛠 {_service_name(row['service_key'])}\n"
                f"💰 {int(row['amount'] or 0):,} تومان\n"
                "📌 درخواست پشتیبانی/بررسی همکار"
            )
            try:
                await B.notify_admins(context.application, text, request_id=rid)
                return await q.message.reply_text("✅ تیکت شما برای مدیریت بات ارسال شد.")
            except Exception:
                log.exception("partner ticket failed")
                return await q.message.reply_text("❌ ارسال تیکت انجام نشد؛ دوباره تلاش کنید.")
        if parts[2] == "edit":
            key = str(row["service_key"])
            st["mode"] = None
            st["editing_request_id"] = rid
            try:
                if key == "fida" and hasattr(B, "fida"):
                    return await B.fida(update, context)
                if key == "print" and hasattr(B, "prt"):
                    return await B.prt(update, context)
                if key == "government" and hasattr(B, "gov"):
                    return await B.gov(update, context)
            except Exception:
                log.exception("partner edit flow failed")
            return await q.message.reply_text("✏️ ویرایش این خدمت از ابتدا شروع می‌شود. لطفاً دوباره اطلاعات را وارد کنید.")

    old_build = TG.build
    def build_with_partner_actions():
        app = old_build()
        from telegram.ext import CallbackQueryHandler
        app.add_handler(CallbackQueryHandler(partner_request_callback, pattern=r"^pr:self:"))
        return app
    TG.build = build_with_partner_actions

    import rubika_v2 as R
    old_handle = R.handle
    def handle(uid, chat, x, u):
        uid_s = str(uid)
        st_before = dict(R.STATE.get(uid_s, {}))
        partner_id = st_before.get("partner")
        before = 0
        if partner_id:
            try:
                row = R.db.conn.execute("SELECT COALESCE(MAX(id),0) AS m FROM requests WHERE user_id=?", (partner_id,)).fetchone()
                before = int(row["m"] or 0)
            except Exception:
                pass
        result = old_handle(uid, chat, x, u)
        if partner_id:
            row = _last_request(R.db, partner_id, before)
            if row:
                text = (
                    "📋 درخواست شما ثبت شد.\n"
                    f"🛠 خدمت: {_service_name(row['service_key'])}\n"
                    f"🎫 کد پیگیری: {row['tracking_code']}\n"
                    f"💰 مبلغ: {int(row['amount'] or 0):,} تومان\n"
                    f"📌 وضعیت: {row['status']}"
                )
                try:
                    R.send(chat, text, [["✏️ ویرایش درخواست"], ["✉️ ارسال تیکت به مدیریت بات"]])
                except Exception:
                    log.exception("failed to send Rubika partner receipt")
                _mirror_rubika_to_telegram(text, row)
                R.STATE[uid_s]["last_partner_request_id"] = int(row["id"])
        return result
    R.handle = handle

    wrapped_handle = R.handle
    def handle_actions(uid, chat, x, u):
        st = R.STATE.setdefault(str(uid), {})
        rid = st.get("last_partner_request_id")
        if rid and x in {"✉️ ارسال تیکت به مدیریت بات", "ارسال تیکت به مدیریت بات"}:
            row = R.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if row:
                _mirror_rubika_to_telegram(
                    "✉️ تیکت همکار از روبیکا\n"
                    f"🎫 {row['tracking_code']}\n"
                    f"🛠 {_service_name(row['service_key'])}\n"
                    f"💰 {int(row['amount'] or 0):,} تومان",
                    row,
                )
                R.send(chat, "✅ تیکت برای مدیریت بات ارسال شد.", R.partner_rows())
                return
        if rid and x in {"✏️ ویرایش درخواست", "ویرایش درخواست"}:
            row = R.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if row:
                key = str(row["service_key"])
                if key == "fida":
                    st["step"] = "fida_phone"
                    R.send(chat, R.T(uid, "phone")); return
                if key == "print":
                    st["step"] = "print"
                    R.send(chat, R.T(uid, "print"), [[("1","🖨 سیاه و سفید"),("2","🎨 رنگی")]]); return
                if key == "government":
                    st["step"] = "gov_doc"
                    R.send(chat, "📄 نوع مدرک را انتخاب کنید:", [[('1','کارت آمایش'),('2','کارت موقت')],[('3','پاسپورت'),('4','دفترچه اقامت')]]); return
        return wrapped_handle(uid, chat, x, u)
    R.handle = handle_actions

    B._partner_request_patch_installed = True
    log.info("partner request UX and Rubika->Telegram bridge installed")
