"""Absolute Telegram ui2 callback owner v30.

Legacy-safe compatibility owner. The universal v47 owner is authoritative;
this layer remains as a compatibility fallback and must never import a removed
final_dispatch symbol.
"""
import inspect
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.callback_v30")
CANCEL = "❌ انصراف"
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
MANAGEMENT = "💬 ارتباط با مدیریت"
SIM_SERVICE = "📱 خدمات سیم کارت"
PANEL = "👥 پنل همکاران"
LOGOUT = "🚪 خروج از پنل"
SERVICE_LABELS = {
    "➕ شارژ حساب": "topup", "🏛 حل مشکل سامانه دولت من": "gov", "🔎 پیگیری کد": "ptrack",
    "📋 سوابق": "phistory", "🪪 فیدای غیر حضوری": "fida", "🖨 خدمات چاپ": "prt",
    "🎫 تیکت به مدیریت": "ticket", "💰 موجودی": "balance",
}

def _awaitable(result): return inspect.isawaitable(result)

async def _call(fn, *args):
    if not callable(fn): return None
    result = fn(*args)
    return await result if _awaitable(result) else result

async def _safe_cancel(update, context, B):
    q = update.callback_query; uid = q.from_user.id; st = B.S.setdefault(uid, {})
    old_lang = st.get("lang", "fa"); partner_id = st.get("partner_id")
    keep = {"lang": old_lang, "status": st.get("status")}
    if partner_id and not st.get("partner_logged_out"):
        keep.update({"partner_id": partner_id, "partner_active": True, "partner_logged_out": False})
    st.clear(); st.update({k:v for k,v in keep.items() if v is not None}); st["mode"] = None
    try: await q.answer()
    except Exception: pass
    if st.get("partner_id") and st.get("partner_active"):
        try: p = B.db.conn.execute("SELECT id,name,phone,balance FROM partners WHERE id=? AND active=1 LIMIT 1", (int(st["partner_id"]),)).fetchone()
        except Exception: p = None
        if p:
            return await q.message.reply_text(f"👥 پنل همکاران\n👤 {p['name'] or '-'}\n📱 {p['phone'] or '-'}\n💰 اعتبار: {int(p['balance'] or 0):,} تومان", reply_markup=B.partner_kb(old_lang))
    return await q.message.reply_text("✅ عملیات لغو شد.", reply_markup=B.main(uid))

async def _dispatch(update, context, B, label):
    q = update.callback_query; uid = q.from_user.id; st = B.S.setdefault(uid, {})
    import telegram_ui_policy_v2 as UI
    fake = UI._fake(update, label)
    if label == CANCEL: return await _safe_cancel(update, context, B)
    if label == IRANCELL:
        try:
            import telegram_irancell_partner_service as IRS
            IRS.PRICE = 980_000
            ensure = getattr(IRS, "_ensure_service", None)
            if ensure: await _call(ensure, B)
            try:
                B.db.conn.execute("UPDATE services SET price=?, active=1 WHERE key=?", (980_000, "irancell_sim_issue"))
                B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("price_irancell_sim", "980000")); B.db.conn.commit()
            except Exception:
                try: B.db.conn.rollback()
                except Exception: pass
            st["mode"] = "irancell_partner_phone"; st.pop("irancell", None)
            await q.message.reply_text("📱 حل مشکل سیم کارت ایرانسل\n\n📱 شماره موبایل ایرانسل که به نام مشترک ثبت شده است را وارد کنید:\n\n💰 هزینه خدمت: ۹۸۰٬۰۰۰ تومان\n💳 مبلغ فقط از شارژ پنل همکار کسر می‌شود.\n\nبعد از ثبت، درخواست همراه با مدرک و جزئیات برای مدیریت ارسال می‌شود.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        except Exception:
            log.exception("Irancell start failed"); await q.message.reply_text("❌ شروع خدمت ایرانسل با خطا مواجه شد؛ موجودی و پنل شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        return
    if label == MANAGEMENT:
        try:
            from telegram_partner_final_router_v29 import _management
            await _management(update, context, B, st)
        except ApplicationHandlerStop: raise
        except Exception:
            log.exception("management start failed"); await q.message.reply_text("❌ ارتباط با مدیریت فعلاً با خطا مواجه شد؛ پنل شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        return
    if label == SIM_SERVICE:
        try:
            fn = getattr(B, "sim_start", None)
            if fn: await _call(fn, fake, context)
            else: await q.message.reply_text("📱 خدمات سیم کارت در حال حاضر فعال نیست.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        except Exception:
            log.exception("SIM service start failed"); await q.message.reply_text("❌ خدمات سیم کارت فعلاً با خطا مواجه شد؛ پنل شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        return
    if label == LOGOUT:
        try:
            fn = getattr(B, "partner_exit", None)
            if fn: await _call(fn, fake, context); return
        except Exception: log.exception("partner logout failed")
        st.clear(); st["lang"] = "fa"; st["partner_logged_out"] = True
        await q.message.reply_text("✅ از پنل همکاران خارج شدید.", reply_markup=B.main(uid)); return
    fn_name = SERVICE_LABELS.get(label)
    if fn_name == "balance":
        pid = st.get("partner_id")
        if not pid: await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid)); return
        row = B.db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
        balance = int(row["balance"] or 0) if row else 0
        await q.message.reply_text(f"💰 اعتبار فعلی شما: {balance:,} تومان", reply_markup=B.partner_kb(st.get("lang", "fa"))); return
    if fn_name == "ticket":
        try:
            from telegram_business_features import _send_ticket_prompt
            await _call(_send_ticket_prompt, fake, B)
        except Exception:
            log.exception("ticket start failed"); await q.message.reply_text("❌ ثبت تیکت فعلاً با خطا مواجه شد؛ پنل شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))
        return
    if fn_name:
        fn = getattr(B, fn_name, None)
        if fn:
            try: await _call(fn, fake, context); return
            except Exception:
                log.exception("service start failed label=%r", label); await q.message.reply_text("❌ اجرای خدمت فعلاً با خطا مواجه شد؛ مرحله شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa"))); return
    # Compatibility fallback: use the stable router that is present in the repo.
    try:
        from telegram_stable_callback import handle
        await handle(update, context, B, label)
        return
    except ApplicationHandlerStop: raise
    except Exception:
        log.exception("v30 stable fallback failed label=%r", label)
        await q.message.reply_text("⛔ این گزینه فعلاً اجرا نشد؛ پنل همکاران شما حفظ شد.", reply_markup=B.partner_kb(st.get("lang", "fa")))

def install(app, B):
    if getattr(B, "_absolute_callback_v30", False): return
    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("ui2:"): return
        token = str(q.data)[4:]
        row = B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)).fetchone()
        if row and row["user_id"] and str(row["user_id"]) != str(q.from_user.id):
            await q.answer("این دکمه متعلق به حساب دیگری است.", show_alert=True); raise ApplicationHandlerStop
        label = str(row["label"] or "").strip() if row else ""
        if not label:
            try:
                for rr in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
                    for b in rr or []:
                        if getattr(b, "callback_data", None) == q.data: label = str(getattr(b, "text", "") or "").strip()
            except Exception: pass
        if not label: return
        await q.answer()
        await _dispatch(update, context, B, label)
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-7000000)
    B._absolute_callback_v30 = True
    log.info("ABSOLUTE Telegram ui2 callback hardening v30 installed (stable fallback)")
