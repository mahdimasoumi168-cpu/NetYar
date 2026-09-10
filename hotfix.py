"""Consolidated reliability layer for NetYar.

Loaded explicitly by server.py before building Telegram.  It deliberately wraps
existing handlers instead of replacing the business logic, so a bad optional
feature cannot take down the core bot.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("netyar.hotfix")


def install():
    import bot as B
    from telegram import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

    if getattr(B, "_netyar_hotfix_installed", False):
        return

    # ---------- Telegram keyboard styling ----------
    def style_for(text):
        s = str(text)
        if any(x in s for x in ("تأیید", "فعال", "شارژ", "ثبت", "ذخیره", "Approve", "Confirm", "Active", "Save")):
            return "success"
        if any(x in s for x in ("انصراف", "رد", "حذف", "لغو", "خروج", "Reject", "Delete", "Cancel", "Exit")):
            return "danger"
        if any(x in s for x in ("مدیریت", "همکار", "پنل", "بات", "زبان", "گزارش", "تنظیمات")):
            return "primary"
        return "primary"

    def styled_kb(rows):
        out = []
        for row in rows or []:
            rr = []
            for item in row or []:
                text = str(item)
                try:
                    rr.append(KeyboardButton(text=text, style=style_for(text)))
                except Exception:
                    rr.append(KeyboardButton(text=text))
            if rr:
                out.append(rr)
        return ReplyKeyboardMarkup(out, resize_keyboard=True, one_time_keyboard=False)

    B.kb = styled_kb

    # ---------- localized main menu ----------
    def main(uid):
        lang = B.S.get(uid, {}).get("lang", "fa")
        if lang == "en":
            rows = [
                ["🪪 FIDA non-in-person", "🖨 Printing"],
                ["🏛 Government access issue", "🎫 Follow-up"],
                ["📱 SIM services", "📝 Screening test"],
                ["💰 My wallet", "📞 Contact us"],
                ["📝 Customer complaints", "👥 Partner panel"],
            ]
            if B.admin(uid): rows.append(["🛠 Admin panel"])
            return B.kb(rows + [["❌ Cancel"]])
        if lang == "ar":
            rows = [
                ["🪪 خدمة فيدا", "🖨 خدمات الطباعة"],
                ["🏛 مشكلة خدمات الحكومة", "🎫 متابعة"],
                ["📱 خدمات الشريحة", "📝 اختبار الفحص"],
                ["💰 محفظتي", "📞 اتصل بنا"],
                ["📝 شكاوى العملاء", "👥 لوحة الشركاء"],
            ]
            if B.admin(uid): rows.append(["🛠 لوحة الإدارة"])
            return B.kb(rows + [["❌ إلغاء"]])
        rows = [
            ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
            ["🏛 حل مشکل ورود اتباع دولت من", "🎫 پیگیری"],
            ["📱 خدمات سیم کارت", "📝 آزمون غربالگری"],
            ["💰 کیف پول من", "📞 تماس با ما"],
            ["📝 ثبت شکایت مشتریان", "👥 پنل همکاران"],
        ]
        if B.admin(uid): rows.append(["🛠 پنل مدیریت بات"])
        return B.kb(rows + [[B.CANCEL]])

    B.main = main

    def partner_kb(lang="fa"):
        if lang == "en":
            return B.kb([["➕ Top up", "🏛 Government access issue"], ["🔎 Track code", "📋 History"], ["💰 Balance"], ["🚪 Exit panel"], ["❌ Cancel"]])
        if lang == "ar":
            return B.kb([["➕ شحن الحساب", "🏛 حل مشكلة خدمات الحكومة"], ["🔎 رمز المتابعة", "📋 السجل"], ["💰 الرصيد"], ["🚪 خروج من اللوحة"], ["❌ إلغاء"]])
        return B.kb([["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🔎 پیگیری کد", "📋 سوابق"], ["💰 موجودی"], ["🚪 خروج از پنل",], [B.CANCEL]])

    B.partner_kb = partner_kb

    def admin_menu():
        return B.kb([
            ["👤 پنل کاربران", "👥 همکاران"],
            ["➕ افزودن همکار", "💰 شارژها"],
            ["📋 درخواست‌ها", "💳 پرداخت‌های مشتری"],
            ["⚙️ قیمت‌ها", "📊 گزارش"],
            ["🤖 افزودن بات", "🤖 بات‌های متصل"],
            ["🌐 زبان‌ها", "🩺 سلامت ربات‌ها"],
            ["⚙️ تنظیمات", "📣 اعلان خدمت"],
            ["⬅️ منوی اصلی"],
        ])

    B.amenu = admin_menu

    # ---------- callback language/status safety ----------
    old_langcb = B.langcb
    old_statuscb = B.statuscb

    async def langcb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        selected = str(q.data or "").split(":", 1)[-1]
        if selected not in {"fa", "en", "ar"}:
            selected = "fa"
        old = B.S.get(uid, {})
        keep = {k: old[k] for k in ("partner_id", "partner_active", "admin", "status") if k in old}
        B.S[uid] = {**keep, "lang": selected, "mode": None}
        texts = {
            "fa": ("آیا اتباع هستید یا ایرانی؟", "🪪 اتباع هستم", "🇮🇷 ایرانی هستم"),
            "en": ("Are you a foreign national or Iranian?", "🪪 Foreign national", "🇮🇷 Iranian"),
            "ar": ("هل أنت أجنبي أم إيراني؟", "🪪 أجنبي", "🇮🇷 إيراني"),
        }
        text, foreign, iranian = texts[selected]
        return await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(foreign, callback_data="st:foreign"), InlineKeyboardButton(iranian, callback_data="st:iranian")]]))

    async def statuscb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        st["status"] = str(q.data or "").split(":", 1)[-1]
        lang = st.get("lang", "fa")
        if st["status"] == "foreign":
            msg = {"fa": "منوی خدمات کمک یار مهاجر 👇", "en": "Immigrant Helper services menu 👇", "ar": "قائمة خدمات المهاجرين 👇"}[lang]
        else:
            msg = {"fa": "🇮🇷 خدمات ایرانی فعلاً فعال نیست.", "en": "🇮🇷 Services for Iranian citizens are currently unavailable.", "ar": "🇮🇷 خدمات المواطنين الإيرانيين غير متاحة حالياً."}[lang]
        return await q.message.reply_text(msg, reply_markup=B.main(uid))

    B.langcb = langcb
    B.statuscb = statuscb

    # ---------- Admin notifications: text + buttons + every uploaded file ----------
    old_notify = B.notify_admins

    async def notify_admins(app, message, request_id=None, inline=None, files=None):
        if not B.ADM:
            return
        file_ids = list(files or [])
        tracking = str(request_id or "")
        if request_id:
            try:
                r = B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?", (request_id,)).fetchone()
                if r: tracking = r["tracking_code"]
                rows = B.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id", (request_id,)).fetchall()
                file_ids.extend(x["file_id"] for x in rows if x["file_id"])
            except Exception:
                log.exception("request file lookup failed")
        if request_id and inline is None:
            inline = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"req:v:{request_id}")],
                [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{request_id}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{request_id}")],
                [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{request_id}")],
                [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{request_id}")],
            ])
        for aid in B.ADM:
            try:
                await app.bot.send_message(chat_id=int(aid), text=message, reply_markup=inline)
                for fid in dict.fromkeys(x for x in file_ids if x):
                    try:
                        await app.bot.send_photo(chat_id=int(aid), photo=fid, caption=f"📎 فایل درخواست {tracking}")
                    except Exception:
                        try:
                            await app.bot.send_document(chat_id=int(aid), document=fid, caption=f"📎 فایل درخواست {tracking}")
                        except Exception:
                            log.exception("admin file forwarding failed")
            except Exception:
                log.exception("admin notification failed")

    B.notify_admins = notify_admins

    # ---------- Partner chat + verification-code bridge ----------
    old_ptext = B.ptext

    async def ptext(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        if pid:
            try:
                B.db.set_setting(f"partner_chat_{pid}", str(update.effective_chat.id))
            except Exception:
                pass
            pending = B.db.setting(f"partner_code_request_{pid}", "")
            if pending:
                rid_s = str(pending).split("|", 1)[0]
                text = (update.message.text or "").strip() if update.message else ""
                if text and text not in {B.CANCEL, "لغو", "❌ لغو", "❌ Cancel", "❌ إلغاء"}:
                    try:
                        rid = int(rid_s)
                        req = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                        if req:
                            B.db.answer(rid, "verification_code", answer=text)
                            B.db.set_setting(f"partner_code_request_{pid}", "")
                            B.db.conn.commit()
                            for aid in B.ADM:
                                try:
                                    await context.bot.send_message(chat_id=int(aid), text=f"🔐 کد تأیید همکار دریافت شد.\n🎫 {req['tracking_code']}\n👥 همکار: {pid}\n🔑 کد: {text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده", callback_data=f"req:v:{rid}"), InlineKeyboardButton("✅ تأیید", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد", callback_data=f"req:x:{rid}")]]))
                                except Exception:
                                    log.exception("verification notification failed")
                            return await update.message.reply_text("✅ کد دریافت شد و برای مدیریت ارسال شد.", reply_markup=partner_kb(st.get("lang", "fa")))
                    except Exception:
                        log.exception("verification code handling failed")
        return await old_ptext(update, context)

    B.ptext = ptext

    # ---------- Request approve/reject/request-code ----------
    old_admin_cb = B.admin_cb

    async def admin_cb(update, context):
        q = update.callback_query
        data = str(q.data or "").split(":")
        if not B.admin(q.from_user.id):
            return
        if data and data[0] == "req" and len(data) >= 3:
            try:
                rid = int(data[2])
            except Exception:
                return await q.answer("درخواست نامعتبر")
            r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if not r:
                await q.answer("درخواست پیدا نشد")
                return
            await q.answer()
            if data[1] == "v":
                ans = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
                details = "\n".join(f"• {x['field_key']}: {x['answer']}" + (" 📎" if x['file_id'] else "") for x in ans) or "• اطلاعات تکمیلی ثبت نشده است."
                return await q.message.reply_text(f"🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n💰 مبلغ: {int(r['amount']):,} تومان\n💳 پرداخت: {r['payment_status']}\n\n{details}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")], [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}"), InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")]]))
            if data[1] in {"a", "x"}:
                status = "approved" if data[1] == "a" else "rejected"
                B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (status, B.now(), rid))
                B.db.conn.commit()
                pid_row = B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1", (rid,)).fetchone()
                pid = str(pid_row["answer"]) if pid_row else ""
                if not pid:
                    p = B.db.conn.execute("SELECT id FROM partners WHERE id=?", (r["user_id"],)).fetchone()
                    pid = str(p["id"]) if p else ""
                msg = "✅ خدمت شما توسط مدیریت تأیید شد." if status == "approved" else "❌ درخواست شما توسط مدیریت رد شد."
                sent = False
                if pid:
                    chat = B.db.setting(f"partner_chat_{pid}", "")
                    if chat:
                        try:
                            await context.bot.send_message(chat_id=int(chat), text=msg, reply_markup=partner_kb())
                            sent = True
                        except Exception:
                            log.exception("partner result notification failed")
                if not sent:
                    user = B.db.conn.execute("SELECT platform,external_id FROM users WHERE id=?", (r["user_id"],)).fetchone()
                    if user and user["platform"] == "telegram":
                        try: await context.bot.send_message(chat_id=int(user["external_id"]), text=msg)
                        except Exception: log.exception("customer result notification failed")
                try: await q.message.edit_reply_markup(reply_markup=None)
                except Exception: pass
                return await q.message.reply_text(msg + "\n📨 نتیجه برای درخواست‌کننده ارسال شد.", reply_markup=B.amenu())
            if data[1] == "p":
                row = B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1", (rid,)).fetchone()
                pid = str(row["answer"]) if row else ""
                if not pid:
                    p = B.db.conn.execute("SELECT id FROM partners WHERE id=?", (r["user_id"],)).fetchone()
                    pid = str(p["id"]) if p else ""
                if not pid:
                    return await q.message.reply_text("⚠️ این درخواست به همکار متصل نیست.", reply_markup=B.amenu())
                B.db.set_setting(f"partner_code_request_{pid}", f"{rid}|{B.now()}")
                chat = B.db.setting(f"partner_chat_{pid}", "")
                if not chat:
                    return await q.message.reply_text("⚠️ همکار هنوز در پنل وارد نشده است؛ ابتدا همکار یک‌بار وارد پنل شود.", reply_markup=B.amenu())
                await context.bot.send_message(chat_id=int(chat), text=f"🔐 مدیریت برای درخواست {r['tracking_code']} کد تأیید همان خدمت را می‌خواهد.\n\nفقط کد تأیید خدمت را ارسال کنید؛ رمز ورود پنل را ارسال نکنید.", reply_markup=partner_kb())
                return await q.message.reply_text("✅ درخواست کد برای همکار ارسال شد.", reply_markup=B.amenu())
        return await old_admin_cb(update, context)

    B.admin_cb = admin_cb

    # ---------- Text aliases: every keyboard label is also accepted as text ----------
    aliases = {
        "🇮🇷 فارسی": "lang:fa", "🇬🇧 English": "lang:en", "🇸🇦 العربية": "lang:ar",
        "🪪 FIDA non-in-person": "🪪 فیدای غیر حضوری", "🖨 Printing": "🖨 خدمات چاپ",
        "🏛 Government access issue": "🪪 حل مشکل ورود اتباع دولت من", "🎫 Follow-up": "🎫 پیگیری",
        "🎫 Track request": "🎫 پیگیری", "📱 SIM services": "📱 خدمات سیم کارت", "📝 Screening test": "📝 آزمون غربالگری",
        "💰 My wallet": "💰 کیف پول من", "📞 Contact us": "📞 تماس با ما", "📝 Customer complaints": "📝 ثبت شکایت مشتریان",
        "👥 Partner panel": "👥 پنل همکاران", "🛠 Admin panel": "🛠 پنل مدیریت بات",
        "🪪 خدمة فيدا": "🪪 فیدای غیر حضوری", "🖨 خدمات الطباعة": "🖨 خدمات چاپ", "🏛 مشكلة خدمات الحكومة": "🪪 حل مشکل ورود اتباع دولت من",
        "🎫 متابعة": "🎫 پیگیری", "📱 خدمات الشريحة": "📱 خدمات سیم کارت", "📝 اختبار الفحص": "📝 آزمون غربالگری",
        "💰 محفظتي": "💰 کیف پول من", "📞 اتصل بنا": "📞 تماس با ما", "📝 شكاوى العملاء": "📝 ثبت شکایت مشتریان", "👥 لوحة الشركاء": "👥 پنل همکاران",
        "🛠 لوحة الإدارة": "🛠 پنل مدیریت بات", "❌ Cancel": B.CANCEL, "❌ إلغاء": B.CANCEL,
        "➕ Top up": "➕ شارژ حساب", "🏛 حل مشكلة خدمات الحكومة": "🏛 حل مشکل سامانه دولت من", "🔎 Track code": "🔎 پیگیری کد",
        "📋 History": "📋 سوابق", "💰 Balance": "💰 موجودی", "🚪 Exit panel": "🚪 خروج از پنل",
    }

    old_router = B.router

    async def router(update, context):
        # MessageHandler may receive edited/non-message updates in PTB; never crash on them.
        if not getattr(update, "message", None):
            return
        text = (update.message.text or "").strip()
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})

        # Language can also be sent as text.
        if text in aliases and aliases[text].startswith("lang:"):
            lang = aliases[text].split(":", 1)[1]
            st.update(lang=lang, mode=None)
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            qtext = {"fa":"آیا اتباع هستید یا ایرانی؟", "en":"Are you a foreign national or Iranian?", "ar":"هل أنت أجنبي أم إيراني؟"}[lang]
            foreign = {"fa":"🪪 اتباع هستم", "en":"🪪 Foreign national", "ar":"🪪 أجنبي"}[lang]
            iranian = {"fa":"🇮🇷 ایرانی هستم", "en":"🇮🇷 Iranian", "ar":"🇮🇷 إيراني"}[lang]
            return await update.message.reply_text(qtext, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(foreign, callback_data="st:foreign"), InlineKeyboardButton(iranian, callback_data="st:iranian")]]))

        canonical = aliases.get(text, text)
        if canonical != text:
            # PTB 22 Message.text is immutable; use a tiny proxy instead of mutating it.
            class MsgProxy:
                def __init__(self, msg, txt): self._msg, self.text = msg, txt
                def __getattr__(self, n): return getattr(self._msg, n)
            class UpdProxy:
                def __init__(self, upd, msg): self._upd, self.message = upd, msg
                def __getattr__(self, n): return getattr(self._upd, n)
            update = UpdProxy(update, MsgProxy(update.message, canonical))

        # Partner verification code takes priority over generic routing.
        if st.get("partner_id") and B.db.setting(f"partner_code_request_{st['partner_id']}", ""):
            return await B.ptext(update, context)
        return await old_router(update, context)

    B.router = router

    # ---------- Rubika text/button normalization ----------
    try:
        import rubika_v2 as RB
        old_handle = RB.handle

        def rb_handle(uid, chat, text, user):
            x = str(text or "").strip()
            aliases_rb = {
                "📝 Screening test":"📝 آزمون غربالگری", "📝 اختبار الفحص":"📝 آزمون غربالگری",
                "🎫 Follow-up":"🎫 پیگیری", "🎫 متابعة":"🎫 پیگیری", "👥 Partner panel":"👥 پنل همکاران",
                "👥 لوحة الشركاء":"👥 پنل همکاران", "🪪 FIDA non-in-person":"🪪 فیدای غیر حضوری",
                "🪪 خدمة فيدا":"🪪 فیدای غیر حضوری", "🖨 Printing":"🖨 خدمات چاپ", "🖨 الطباعة":"🖨 خدمات چاپ",
                "📱 SIM services":"📱 خدمات سیم کارت", "📱 خدمات الشريحة":"📱 خدمات سیم کارت",
                "💰 My wallet":"💰 کیف پول من", "💰 محفظتي":"💰 کیف پول من", "📞 Contact us":"📞 تماس با ما", "📞 اتصل بنا":"📞 تماس با ما",
                "❌ Cancel": RB.CANCEL, "❌ إلغاء": RB.CANCEL,
            }
            return old_handle(uid, chat, aliases_rb.get(x, x), user)

        RB.handle = rb_handle
    except Exception:
        log.exception("Rubika handler patch failed")

    B._netyar_hotfix_installed = True
    log.info("NetYar consolidated hotfix installed")
