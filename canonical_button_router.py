"""Canonical final Telegram button routing and navigation owner."""
import logging
log = logging.getLogger("netyar.canonical_buttons")


def install():
    import bot as B
    import telegram_runtime as TG
    from telegram import CallbackQueryHandler, InlineKeyboardMarkup, InlineKeyboardButton
    from final_platform_fix import _actions
    from final_ui_flow_patch import _UI

    if getattr(B, "_canonical_button_router", False): return

    old_main = B.main
    def main(uid):
        st = B.S.get(uid, {})
        if st.get("status") == "iranian":
            rows = [["🎫 پیگیری", "👥 پنل همکاران"], ["🔄 شروع مجدد"]]
            if B.admin(uid): rows.append(["🛠 پنل مدیریت بات"])
            return B.kb(rows)
        rows = [
            ["🪪 فیدای غیر حضوری", "🖨 خدمات چاپ"],
            ["🪪 حل مشکل ورود اتباع دولت من", "🎫 کد رهگیری تمدید کارت‌ها"],
            ["📱 خدمات سیم کارت", "📝 آزمون غربالگری"],
            ["🎫 پیگیری", "💰 کیف پول من"],
            ["📞 تماس با ما", "📝 ثبت شکایت مشتریان"],
            ["👥 پنل همکاران", "🔄 شروع مجدد"],
        ]
        if B.admin(uid): rows.append(["🛠 پنل مدیریت بات"])
        return B.kb(rows)
    B.main = main

    async def statuscb(update, context):
        q = update.callback_query; await q.answer(); uid = q.from_user.id
        status = str(q.data).split(":", 1)[1]
        B.S.setdefault(uid, {})["status"] = status
        if status == "iranian":
            return await q.message.reply_text("🇮🇷 بخش خدمات ایرانی\n\nفعلاً خدمات عمومی برای ایرانی فعال نیست.", reply_markup=B.main(uid))
        return await q.message.reply_text("منوی خدمات کمک یار مهاجر 👇", reply_markup=B.main(uid))
    B.statuscb = statuscb

    aliases = {
        "🔵 👥 پنل همکاران":"👥 پنل همکاران", "🔵 👥 Partner panel":"👥 پنل همکاران", "🔵 👥 لوحة الشركاء":"👥 پنل همکاران",
        "👥 Partner panel":"👥 پنل همکاران", "👥 لوحة الشركاء":"👥 پنل همکاران", "پنل همکاران":"👥 پنل همکاران",
        "🔵 🛠 پنل مدیریت بات":"🛠 پنل مدیریت بات", "🛠 پنل مدیریت":"🛠 پنل مدیریت بات", "🛠 Admin panel":"🛠 پنل مدیریت بات", "🛠 لوحة الإدارة":"🛠 پنل مدیریت بات",
        "🎫 Tracking":"🎫 پیگیری", "🎫 متابعة":"🎫 پیگیری", "🪪 FIDA non-in-person":"🪪 فیدای غیر حضوری", "🖨 Printing":"🖨 خدمات چاپ",
        "🏛 Government access issue":"🪪 حل مشکل ورود اتباع دولت من", "🎫 Tracking code":"🎫 کد رهگیری تمدید کارت‌ها", "📱 SIM services":"📱 خدمات سیم کارت",
        "📝 Screening test":"📝 آزمون غربالگری", "❌ Cancel":"❌ انصراف", "❌ إلغاء":"❌ انصراف", "❌ لغو":"❌ انصراف", "لغو":"❌ انصراف", "انصراف":"❌ انصراف",
        "🔄 شروع دوباره":"🔄 شروع مجدد", "Restart":"🔄 شروع مجدد", "Start again":"🔄 شروع مجدد", "بدء من جديد":"🔄 شروع مجدد",
        "📋 سوابق":"📋 سوابق", "History":"📋 سوابق", "📋 السجل":"📋 سوابق",
    }
    def norm(x): return aliases.get(str(x or "").strip(), str(x or "").strip())

    # Final text router: reply-keyboard buttons must work even when an older
    # router has a narrower alias table.
    old_router = B.router
    async def canonical_router(update, context):
        uid = int(update.effective_user.id)
        text = norm(getattr(getattr(update, "message", None), "text", ""))
        st = B.S.setdefault(uid, {})
        try:
            if text == "🔄 شروع مجدد":
                B.S[uid] = {}
                return await B.start(update, context)
            if text == "👥 پنل همکاران":
                return await B.partner(update, context)
            if text == "🛠 پنل مدیریت بات":
                if not B.admin(uid):
                    return await update.message.reply_text("❌ دسترسی مدیریت ندارید.", reply_markup=B.main(uid))
                return await update.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            if text == "🚪 خروج از پنل":
                return await B.partner_exit(update, context)
            if text == "❌ انصراف":
                return await B.cancel(update, context)
            if text == "📋 سوابق" and st.get("partner_id"):
                return await B.phistory(update, context)
        except Exception:
            log.exception("canonical text button failed: %r", text)
            return await update.message.reply_text("❌ اجرای گزینه با خطا مواجه شد؛ لطفاً دوباره تلاش کنید.", reply_markup=B.main(uid))
        return await old_router(update, context)
    B.router = canonical_router

    # Make previous partner requests actionable instead of a plain text dump.
    old_phistory = B.phistory
    async def phistory(update, context):
        uid = int(update.effective_user.id)
        st = B.S.get(uid, {})
        pid = st.get("partner_id")
        if not pid:
            return await B.partner(update, context)
        rows = B.db.conn.execute(
            "SELECT id,tracking_code,service_key,status,amount,created_at FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (pid,),
        ).fetchall()
        if not rows:
            return await update.message.reply_text("📋 سابقه‌ای برای این همکار ثبت نشده است.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        lines = ["📋 درخواست‌های قبلی شما\n"]
        buttons = []
        for r in rows:
            lines.append(f"🎫 {r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount'] or 0):,} تومان")
            buttons.append([InlineKeyboardButton(f"🔎 مشاهده {r['tracking_code']}", callback_data=f"prevreq:{r['id']}")])
        buttons.append([InlineKeyboardButton("🔙 بازگشت به پنل همکاران", callback_data="prevreq:back")])
        return await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
    B.phistory = phistory

    async def previous_request_callback(update, context):
        q = update.callback_query
        uid = int(q.from_user.id)
        st = B.S.setdefault(uid, {})
        if not st.get("partner_id"):
            await q.answer("ابتدا وارد پنل همکاران شوید.")
            return
        value = str(q.data or "").split(":", 1)[-1]
        if value == "back":
            await q.answer()
            return await q.message.reply_text("👥 پنل همکاران", reply_markup=B.partner_kb(st.get("lang", "fa")))
        try:
            rid = int(value)
        except Exception:
            await q.answer("درخواست نامعتبر است.")
            return
        r = B.db.conn.execute("SELECT * FROM requests WHERE id=? AND user_id=?", (rid, st["partner_id"])).fetchone()
        if not r:
            await q.answer("درخواست پیدا نشد.")
            return
        await q.answer()
        ans = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
        details = "\n".join(f"• {x['field_key']}: {x['answer']}" + (" 📎" if x['file_id'] else "") for x in ans) or "• اطلاعات تکمیلی ثبت نشده است."
        return await q.message.reply_text(
            f"📋 جزئیات درخواست قبلی\n\n🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n💰 مبلغ: {int(r['amount'] or 0):,} تومان\n💳 پرداخت: {r['payment_status']}\n\n{details}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✉️ ارسال تیکت به مدیریت", callback_data=f"pr:self:ticket:{rid}")], [InlineKeyboardButton("🔙 سوابق", callback_data="prevreq:back")]])
        )

    async def dispatch(update, context):
        q = update.callback_query; data = str(q.data or "")
        if data.startswith("prevreq:"):
            return await previous_request_callback(update, context)
        label = ""
        if data.startswith("ik:"): label = norm(_actions.get(data, ""))
        elif data.startswith("ui:"): label = norm(_UI.get(data, (None, ""))[1])
        if not label:
            await q.answer("این گزینه منقضی شده؛ لطفاً /start را بزنید."); return
        await q.answer(); uid = q.from_user.id; st = B.S.setdefault(uid, {})
        try:
            if label == "🔄 شروع مجدد":
                B.S[uid] = {}
                return await B.start(update, context)
            if label == "👥 پنل همکاران":
                # CallbackQuery has no .message on Update; call partner with a tiny adapter.
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                return await B.partner(fake, context)
            if label == "🛠 پنل مدیریت بات":
                if not B.admin(uid): return await q.message.reply_text("❌ دسترسی مدیریت ندارید.", reply_markup=B.main(uid))
                return await q.message.reply_text("🛠 پنل مدیریت", reply_markup=B.amenu())
            if label == "🚪 خروج از پنل":
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                return await B.partner_exit(fake, context)
            if label == "❌ انصراف":
                fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
                return await B.cancel(fake, context)
            fake = type("U", (), {"effective_user":q.from_user,"message":q.message})()
            q.message.text = label
            if label == "🎫 پیگیری" and st.get("status") == "iranian": return await B.service_text(fake, context)
            if label == "🎫 پیگیری": return await B.ptext(fake, context)
            if label == "➕ شارژ حساب":
                st["mode"] = "topup_amount"
                return await q.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            if label == "🔎 پیگیری کد": return await B.ptrack(fake, context)
            if label == "📋 سوابق": return await B.phistory(fake, context)
            if label == "💰 موجودی": return await B.router(fake, context)
            if label in {"🪪 فیدای غیر حضوری", "🪪 فیدا"}: return await B.fida(fake, context)
            if label == "🖨 خدمات چاپ": return await B.prt(fake, context)
            if label in {"🪪 حل مشکل ورود اتباع دولت من", "🏛 حل مشکل سامانه دولت من"}: return await B.gov(fake, context)
            if B.admin(uid):
                result = await B.admin_text(fake, context)
                if result is not None: return result
            result = await B.router(fake, context)
            if result is not None: return result
            return await q.message.reply_text("❌ این گزینه در حال حاضر در دسترس نیست.", reply_markup=B.main(uid))
        except Exception:
            log.exception("canonical button failed: %r", label)
            try: await q.message.reply_text("❌ اجرای گزینه با خطا مواجه شد.", reply_markup=B.main(uid))
            except Exception: pass

    old_build = TG.build
    def build():
        app = old_build()
        app.add_handler(CallbackQueryHandler(previous_request_callback, pattern=r"^prevreq:"), group=-101)
        app.add_handler(CallbackQueryHandler(dispatch, pattern=r"^(ui|ik):"), group=-100)
        return app
    TG.build = build
    B._canonical_button_router = True
    log.info("Canonical final Telegram button router installed")
