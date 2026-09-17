"""Last runtime consistency layer for Telegram.

Loaded after all legacy/final overlays. It makes the night switch authoritative
for night-worker access and pins the Irancell partner service to 300,000 Toman.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.runtime_finalizer")
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
PRICE = 300_000


def _admin_ids(B):
    raw = getattr(B, "ADM", ()) or getattr(B, "ADMINS", ()) or ()
    if isinstance(raw, (str, int)):
        raw = (raw,)
    out=[]
    for x in raw:
        try: out.append(int(x))
        except Exception: pass
    return list(dict.fromkeys(out))


def _service_setup(B):
    import telegram_irancell_partner_service as S
    S.PRICE = PRICE
    S._ensure_service(B)
    B.db.conn.execute("UPDATE services SET price=?,active=1,description=? WHERE key=?", (PRICE,"حل مشکل سیم کارت ایرانسل از طریق پنل همکاران",S.SERVICE_KEY))
    B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",("price_irancell_sim",str(PRICE)))
    B.db.conn.commit()


def _partner_markup(B,uid):
    import telegram_ui_policy_v2 as UI
    return UI.inline([
        ["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],
        [IRANCELL,"🪪 فیدای غیر حضوری"],
        ["📱 خدمات سیم کارت","🔎 پیگیری کد"],
        ["📋 سوابق","💰 موجودی"],
        ["🎫 تیکت به مدیریت","💬 ارتباط با مدیریت"],
        ["🚪 خروج از پنل"],["❌ انصراف"]],B,uid)


async def _start_irancell(update,context,B):
    q=update.callback_query; uid=q.from_user.id; st=B.S.setdefault(uid,{})
    if not st.get("partner_id") or not st.get("partner_active",False) or st.get("partner_logged_out"):
        await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.",reply_markup=_partner_markup(B,uid)); raise ApplicationHandlerStop
    _service_setup(B)
    st["mode"]="irancell_partner_phone"; st.pop("irancell",None)
    await q.answer()
    await q.message.reply_text("📱 حل مشکل سیم کارت ایرانسل\n\n📱 شماره موبایل ایرانسل که به نام مشترک ثبت شده است را وارد کنید:\n\n💰 هزینه خدمت: ۳۰۰٬۰۰۰ تومان\n💳 مبلغ فقط از شارژ پنل همکار کسر می‌شود.\n\nبعد از ثبت، درخواست همراه با مدرک و جزئیات برای مدیریت ارسال می‌شود.",reply_markup=B.cancel_kb(st.get("lang","fa")))
    raise ApplicationHandlerStop


async def _irancell_admin_callback(update,context,B):
    q=update.callback_query; data=str(q.data or "")
    if not q or not data.startswith("irsim:") or not B.admin(q.from_user.id): return
    try: rid=int(data.rsplit(":",1)[1])
    except Exception: await q.answer("شناسه درخواست نامعتبر است",show_alert=True); raise ApplicationHandlerStop
    row=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
    if not row: await q.answer("درخواست پیدا نشد",show_alert=True); raise ApplicationHandlerStop
    action=data.split(":",1)[1].rsplit(":",1)[0]
    await q.answer()
    if action in {"detail","last"}:
        lines=["📱 درخواست حل مشکل سیم کارت ایرانسل","",f"🎫 کد پیگیری: {row['tracking_code']}",f"📌 وضعیت: {row['status']}",f"📱 شماره مشترک: "+"-"]
        answers=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
        for a in answers:
            if a['answer']: lines.append(f"📋 {a['field_key']}: {a['answer']}")
        lines.append(f"💰 مبلغ: {int(row['amount'] or 0):,} تومان")
        await q.message.reply_text("\n".join(lines),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"irsim:review:{rid}")],[InlineKeyboardButton("✅ تأیید درخواست",callback_data=f"irsim:approve:{rid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"irsim:reject:{rid}")],[InlineKeyboardButton("🔐 درخواست کد امنیتی",callback_data=f"panel:askcode:{rid}")]]))
        try:
            files=B.db.conn.execute("SELECT file_id,file_type,caption FROM request_files WHERE request_id=? ORDER BY id",(rid,)).fetchall()
            for f in files:
                if f['file_id']:
                    try: await q.message.reply_document(document=f['file_id'],caption=f['caption'] or '📎 مدرک درخواست')
                    except Exception: await q.message.reply_photo(photo=f['file_id'],caption=f['caption'] or '📎 مدرک درخواست')
        except Exception: log.exception("Irancell attachment read failed")
        raise ApplicationHandlerStop
    if action in {"approve","reject","review"}:
        status={"approve":"completed","reject":"rejected","review":"reviewing"}[action]
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid)); B.db.conn.commit()
        await q.message.reply_text({"approve":"✅ درخواست تأیید و انجام شد.","reject":"❌ درخواست رد شد.","review":"⏳ درخواست وارد بررسی شد."}[action])
        raise ApplicationHandlerStop


def install(app,B):
    if getattr(B,"_runtime_finalizer_v1",False): return True
    try: _service_setup(B)
    except Exception: log.exception("Irancell setup failed")
    try:
        import telegram_partner_main_guard as G
        G.install(app,B)
        try: _service_setup(B)
        except Exception: pass
    except Exception: log.exception("partner guard final install failed")
    try:
        import telegram_night_shift_v2 as N
        from telegram_offhours_partner_gate_v2 import night_shift_enabled
        original=getattr(N,"allowed",None)
        if callable(original):
            def allowed(B_,uid,update=None):
                try:
                    if B_.admin(uid): return True
                except Exception: pass
                try:
                    if not night_shift_enabled(B_): return False
                except Exception: return False
                return bool(original(B_,uid,update))
            N.allowed=allowed
    except Exception: log.exception("night access finalization failed")
    app.add_handler(CallbackQueryHandler(lambda u,c:_start_irancell(u,c,B),pattern=r"^irancell:final$"),group=-90000)
    app.add_handler(CallbackQueryHandler(lambda u,c:_irancell_admin_callback(u,c,B),pattern=r"^irsim:(detail|last|approve|reject|review):"),group=-89999)
    B._runtime_finalizer_v1=True
    log.info("RUNTIME FINALIZER V1 active: night switch authoritative; Irancell price=300000")
    return True
