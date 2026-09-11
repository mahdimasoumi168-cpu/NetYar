"""Final UX hardening layer.

Keeps the existing business handlers intact while fixing:
- Telegram inline callbacks surviving process restarts.
- Iranian menu and support routing.
- Blue partner/admin menu labels.
- Multiple admin IDs via ADMIN_IDS/ADMIN_ID_2.
- Rubika Iranian menu and partner password/phone compatibility.
"""
import os
import re
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("netyar.final_ux_hardening")


def _norm_phone(value):
    s = str(value or "").strip()
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s()\-]", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    return s


def _admins(existing):
    vals = set(existing or set())
    raw = os.getenv("ADMIN_IDS", "")
    vals.update(x.strip() for x in re.split(r"[;,\s]+", raw) if x.strip())
    for key in ("ADMIN_ID_1", "ADMIN_ID_2"):
        v = os.getenv(key, "").strip()
        if v:
            vals.add(v)
    return vals


def install():
    import bot as B
    import final_ui_flow_patch as F

    if getattr(B, "_final_ux_hardening_installed", False):
        return

    # ---------------- persistent Telegram callback registry ----------------
    try:
        B.db.conn.execute(
            "CREATE TABLE IF NOT EXISTS ui_callbacks (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        B.db.conn.commit()
    except Exception:
        log.exception("cannot create persistent UI callback table")

    old_remember = F._remember

    def remember(uid, label):
        token = old_remember(uid, label)
        try:
            B.db.conn.execute(
                "INSERT OR REPLACE INTO ui_callbacks(token,user_id,label,created_at) VALUES(?,?,?,?)",
                (token, str(uid), str(label), B.now()),
            )
            B.db.conn.execute(
                "DELETE FROM ui_callbacks WHERE created_at < ?",
                ((datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),),
            )
            B.db.conn.commit()
        except Exception:
            log.exception("persisting UI callback failed")
        return token

    F._remember = remember

    async def persistent_callback(update, context):
        q = update.callback_query
        await q.answer()
        token = str(q.data or "")
        entry = F._UI.get(token)
        if not entry:
            try:
                row = B.db.conn.execute(
                    "SELECT user_id,label FROM ui_callbacks WHERE token=?",
                    (token,),
                ).fetchone()
                if row:
                    entry = (int(row[0]), row[1])
                    F._UI[token] = entry
            except Exception:
                log.exception("loading persistent UI callback failed")
        if not entry:
            # This is now only for genuinely unknown/old callbacks, not normal restarts.
            return await q.message.reply_text("❌ این گزینه دیگر معتبر نیست. لطفاً منوی جدید را باز کنید.")
        owner, label = entry
        # Never trust the owner stored by an old process; Telegram's sender is authoritative.
        fake = F._fake_update(update, label)
        try:
            result = await B.router(fake, context)
            if result is None:
                if await B.ptext(fake, context):
                    return
                await B.service_text(fake, context)
        except Exception:
            log.exception("persistent inline callback failed: %s", label)
            await q.message.reply_text("❌ اجرای گزینه با خطا روبه‌رو شد. دوباره تلاش کنید.")

    F._ui_callback = persistent_callback

    # ---------------- Telegram menus / Iranian path / support ----------------
    old_main = B.main

    def main(uid):
        lang = B.S.get(uid, {}).get("lang", "fa")
        if lang == "en":
            rows = [
                ["🪪 FIDA service", "🖨 Printing"],
                ["🏛 Government access", "🎫 Tracking"],
                ["📱 SIM services", "📝 Screening"],
                ["🎫 Follow-up", "💰 My wallet"],
                ["📞 Contact us", "📝 Customer complaint"],
                ["🔵 👥 Partner panel"],
            ]
        elif lang == "ar":
            rows = [
                ["🪪 خدمة فيدا", "🖨 خدمات الطباعة"],
                ["🏛 خدمات الحكومة", "🎫 المتابعة"],
                ["📱 خدمات الشريحة", "📝 الفحص"],
                ["🎫 متابعة الطلب", "💰 محفظتي"],
                ["📞 اتصل بنا", "📝 شكوى العميل"],
                ["🔵 👥 لوحة الشركاء"],
            ]
        else:
            rows = [
                ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
                ["🏛 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها"],
                ["📱 خدمات سیم کارت", "📝 آزمون غربالگری"],
                ["🎫 پیگیری", "💰 کیف پول من"],
                ["📞 تماس با ما", "📝 ثبت شکایت مشتریان"],
                ["🔵 👥 پنل همکاران"],
            ]
        if B.admin(uid):
            rows.append(["🔵 🛠 پنل مدیریت بات"])
        rows.append([B.CANCEL])
        B._ui_current_uid = uid
        return B.kb(rows)

    B.main = main

    def iranian_menu(uid):
        B._ui_current_uid = uid
        lang = B.S.get(uid, {}).get("lang", "fa")
        if lang == "en":
            rows = [["🎫 Tracking"], ["🔵 👥 Partner panel"], [B.CANCEL]]
        elif lang == "ar":
            rows = [["🎫 المتابعة"], ["🔵 👥 لوحة الشركاء"], [B.CANCEL]]
        else:
            rows = [["🎫 پیگیری"], ["🔵 👥 پنل همکاران"], [B.CANCEL]]
        return B.kb(rows)

    old_status = B.statuscb
    async def statuscb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        status = str(q.data or "").split(":", 1)[-1]
        B.S.setdefault(uid, {})["status"] = status
        if status == "iranian":
            lang = B.S[uid].get("lang", "fa")
            text = {"fa": "🇮🇷 منوی خدمات ایرانی 👇", "en": "🇮🇷 Iranian user menu 👇", "ar": "🇮🇷 قائمة المستخدم الإيراني 👇"}.get(lang, "🇮🇷 منوی خدمات ایرانی 👇")
            return await q.message.reply_text(text, reply_markup=iranian_menu(uid))
        lang = B.S[uid].get("lang", "fa")
        text = {"fa": "منوی خدمات کمک یار مهاجر 👇", "en": "Mohajer Helper services 👇", "ar": "خدمات مساعد المهاجر 👇"}.get(lang, "منوی خدمات کمک یار مهاجر 👇")
        return await q.message.reply_text(text, reply_markup=main(uid))

    B.statuscb = statuscb

    old_router = B.router
    async def router(update, context):
        uid = update.effective_user.id
        text = (getattr(update.message, "text", "") or "").strip()
        lang = B.S.get(uid, {}).get("lang", "fa")
        contact = {"📞 تماس با ما", "📞 Contact us", "📞 اتصل بنا"}
        partners = {"🔵 👥 پنل همکاران", "🔵 👥 Partner panel", "🔵 👥 لوحة الشركاء", "👥 پنل همکاران"}
        tracking = {"🎫 پیگیری", "🎫 Tracking", "🎫 المتابعة", "🎫 Follow-up"}
        if text in contact:
            support = "@Good_ok_2000"
            msg = {
                "fa": f"📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی به این آیدی پیام دهید:\n{support}",
                "en": f"📞 Support\n\nContact support at:\n{support}",
                "ar": f"📞 الدعم\n\nللتواصل مع الدعم:\n{support}",
            }.get(lang, f"📞 پشتیبانی\n{support}")
            return await update.message.reply_text(msg, reply_markup=main(uid))
        if text in partners:
            return await B.partner(update, context)
        if text in tracking:
            return await B.ptrack(update, context)
        if B.S.get(uid, {}).get("status") == "iranian":
            # Keep Iranian users limited to tracking, partner panel and cancel.
            return await update.message.reply_text(
                {"fa": "لطفاً یکی از گزینه‌های منوی ایرانی را انتخاب کنید.", "en": "Please choose an option from the Iranian menu.", "ar": "يرجى اختيار أحد خيارات القائمة الإيرانية."}.get(lang, "لطفاً یکی از گزینه‌ها را انتخاب کنید."),
                reply_markup=iranian_menu(uid),
            )
        return await old_router(update, context)

    B.router = router

    # ---------------- two-admin support ----------------
    B.ADM = _admins(getattr(B, "ADM", set()))
    try:
        import rubika_v2 as R
        R.ADMIN_IDS = _admins(getattr(R, "ADMIN_IDS", set()))

        old_r_handle = R.handle

        def rubika_handle(uid, chat, x, u):
            uid_s = str(uid)
            st = R.STATE.setdefault(uid_s, {"lang": "fa", "step": "language"})
            # Iranian menu: do not emit the old "services unavailable" message.
            if st.get("step") == "citizenship" and x in {"2", "🇮🇷 ایرانی هستم", "🇮🇷 Iranian", "🇮🇷 إيراني"}:
                st["step"] = "iranian_menu"
                R.send(chat, {"fa": "🇮🇷 منوی خدمات ایرانی 👇", "en": "🇮🇷 Iranian user menu 👇", "ar": "🇮🇷 قائمة المستخدم الإيراني 👇"}.get(st.get("lang", "fa"), "🇮🇷 منوی خدمات ایرانی 👇"), [[("1", "🎫 پیگیری")], [("2", "🔵 👥 پنل همکاران")], [("0", R.CANCEL)]])
                return
            if st.get("step") == "iranian_menu":
                if x in {"1", "🎫 پیگیری", "🎫 Tracking", "🎫 متابعة"}:
                    st["step"] = "track"; R.send(chat, R.T(uid, "track")); return
                if x in {"2", "🔵 👥 پنل همکاران", "👥 پنل همکاران"}:
                    st["step"] = "partner_phone"; R.send(chat, R.T(uid, "partner_phone")); return
                if x in {"0", R.CANCEL, "انصراف", "لغو", "Cancel", "cancel", "إلغاء"}:
                    R.cancel(uid, chat); return
                R.send(chat, R.T(uid, "bad"), [[("1", "🎫 پیگیری")], [("2", "🔵 👥 پنل همکاران")], [("0", R.CANCEL)]])
                return
            # Normalize partner phone before the legacy handler sees it.
            if st.get("step") == "partner_phone":
                st["partner_phone"] = _norm_phone(x)
                if not st["partner_phone"]:
                    R.send(chat, "❌ شماره همراه معتبر نیست.")
                    return
                st["step"] = "partner_pass"
                R.send(chat, R.T(uid, "partner_pass")); return
            # The legacy Rubika handler passed password/hash in the wrong order.
            if st.get("step") == "partner_pass":
                phone = st.get("partner_phone")
                p = R.db.get_partner(phone)
                if not p:
                    R.send(chat, R.T(uid, "no_partner"), [[("0", R.CANCEL)]])
                    return
                if not R.check_password(x, p["password_hash"]):
                    R.send(chat, R.T(uid, "bad_login")); return
                st["partner"] = phone; st["step"] = "partner"
                R.send(chat, f"👥 پنل همکار\n{R.T(uid, 'balance', amount=R.db.get_balance(phone))}", R.partner_rows()); return
            # Support ID is consistent across languages.
            if x in {"9", "📞 تماس با ما", "📞 Contact us", "📞 اتصل بنا"} and st.get("step") in {"main", "service"}:
                R.send(chat, f"📞 پشتیبانی: @Good_ok_2000", R.main_rows(uid)); return
            return old_r_handle(uid, chat, x, u)

        R.handle = rubika_handle
    except Exception:
        log.exception("Rubika hardening could not be installed")

    B._final_ux_hardening_installed = True
    log.info("final UX hardening installed")
