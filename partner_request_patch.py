"""Partner request UX and cross-platform admin bridge with language preservation."""
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


def _request_lang(request_row):
    """Resolve the language from the request owner's current selected state."""
    try:
        platform = str(request_row["platform"] or "").lower()
        import bot as B
        u = B.db.conn.execute("SELECT external_id FROM users WHERE id=?", (request_row["user_id"],)).fetchone()
        ext = str(u["external_id"] or "") if u else ""
        if platform == "rubika":
            import rubika_v2 as R
            value = str(R.STATE.get(ext, {}).get("lang", "fa"))
        else:
            st = getattr(B, "S", {}).get(int(ext), {}) if ext.isdigit() else {}
            value = str(st.get("lang", "fa"))
        return value if value in {"fa", "en", "ar"} else "fa"
    except Exception:
        return "fa"


def _localize(text, lang):
    if lang == "fa":
        return str(text)
    try:
        from telegram_notification_guard import _localize_text
        return _localize_text(text, lang)
    except Exception:
        return str(text)


def _telegram_admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    return [x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip() and x.strip().isdigit()]


def _mirror_rubika_to_telegram(text, request_row=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or os.getenv("BOT_TOKEN", "").strip()
    admins = _telegram_admin_ids()
    if not token or not admins:
        log.warning("Rubika->Telegram bridge skipped: Telegram token/admin ids are not configured")
        return
    lang = _request_lang(request_row) if request_row else "fa"
    payload_text = _localize("📥 درخواست جدید از روبیکا\n\n", lang) + _localize(str(text), lang)
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
                lang = str(st.get("lang", "fa")) if str(st.get("lang", "fa")) in {"fa", "en", "ar"} else "fa"
                text = _localize(
                    "📋 درخواست شما ثبت شد.\n\n"
                    f"🛠 خدمت: {_service_name(row['service_key'])}\n"
                    f"🎫 کد پیگیری: {row['tracking_code']}\n"
                    f"💰 مبلغ: {int(row['amount'] or 0):,} تومان\n"
                    f"📌 وضعیت: {row['status']}\n\n"
                    "از گزینه‌های زیر استفاده کنید:", lang)
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                labels = {"fa": ("✏️ ویرایش درخواست", "✉️ ارسال تیکت به مدیریت بات"), "en": ("✏️ Edit request", "✉️ Send ticket to bot management"), "ar": ("✏️ تعديل الطلب", "✉️ إرسال تذكرة إلى الإدارة")}[lang]
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(labels[0], callback_data=f"pr:self:edit:{row['id']}")],
                    [InlineKeyboardButton(labels[1], callback_data=f"pr:self:ticket:{row['id']}")],
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
        lang = str(st.get("lang", "fa")) if str(st.get("lang", "fa")) in {"fa", "en", "ar"} else "fa"
        if int(st.get("partner_id") or -1) != int(row["user_id"]):
            return await q.message.reply_text(_localize("❌ این درخواست متعلق به شما نیست.", lang))
        if parts[2] == "ticket":
            text = _localize(
                "✉️ تیکت همکار\n"
                f"🎫 {row['tracking_code']}\n"
                f"🛠 {_service_name(row['service_key'])}\n"
                f"💰 {int(row['amount'] or 0):,} تومان\n"
                "📌 درخواست پشتیبانی/بررسی همکار", lang)
            try:
                await B.notify_admins(context.application, text, request_id=rid)
                return await q.message.reply_text(_localize("✅ تیکت شما برای مدیریت بات ارسال شد.", lang))
            except Exception:
                log.exception("partner ticket failed")
                return await q.message.reply_text(_localize("❌ ارسال تیکت انجام نشد؛ دوباره تلاش کنید.", lang))
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
            return await q.message.reply_text(_localize("✏️ ویرایش این خدمت از ابتدا شروع می‌شود. لطفاً دوباره اطلاعات را وارد کنید.", lang))

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
                lang = str(st_before.get("lang", "fa")) if str(st_before.get("lang", "fa")) in {"fa", "en", "ar"} else "fa"
                text = _localize(
                    "📋 درخواست شما ثبت شد.\n"
                    f"🛠 خدمت: {_service_name(row['service_key'])}\n"
                    f"🎫 کد پیگیری: {row['tracking_code']}\n"
                    f"💰 مبلغ: {int(row['amount'] or 0):,} تومان\n"
                    f"📌 وضعیت: {row['status']}", lang)
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
        lang = str(st.get("lang", "fa")) if str(st.get("lang", "fa")) in {"fa", "en", "ar"} else "fa"
        if rid and x in {"✉️ ارسال تیکت به مدیریت بات", "ارسال تیکت به مدیریت بات"}:
            row = R.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if row:
                _mirror_rubika_to_telegram(_localize(
                    "✉️ تیکت همکار از روبیکا\n"
                    f"🎫 {row['tracking_code']}\n"
                    f"🛠 {_service_name(row['service_key'])}\n"
                    f"💰 {int(row['amount'] or 0):,} تومان", lang), row)
                R.send(chat, _localize("✅ تیکت برای مدیریت بات ارسال شد.", lang), R.partner_rows())
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
    log.info("partner request UX and Rubika->Telegram bridge installed with language preservation")