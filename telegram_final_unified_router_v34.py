"""NetYar Telegram unified callback/session hardening v34."""
from __future__ import annotations
import inspect
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.unified_v34")
TRUST_URL = "https://trustseal.enamad.ir/?id=7717012&Code=hEHTsn6HzG7ZsxeorkqzvLbTkOTEpRbH"
SIZPAY_URL = "https://netyarmohajer.sizpay.ir"
PARTNER_LABELS = {
    "➕ شارژ حساب":"topup", "🏛 حل مشکل سامانه دولت من":"gov", "📱 خدمات سیم کارت":"sim",
    "📱 حل مشکل سیم کارت ایرانسل":"irancell", "🪪 فیدای غیر حضوری":"fida", "🔎 پیگیری کد":"ptrack",
    "📋 سوابق":"phistory", "💰 موجودی":"balance", "🎫 تیکت به مدیریت":"ticket",
    "💬 ارتباط با مدیریت":"management", "🚪 خروج از پنل":"logout", "❌ انصراف":"cancel",
}

def _call(fn,*args):
    if not callable(fn): return None
    result=fn(*args)
    return result

async def _await_call(fn,*args):
    result=_call(fn,*args)
    if inspect.isawaitable(result): return await result
    return result

def _partner_ok(B,uid):
    st=B.S.setdefault(uid,{})
    if st.get("partner_logged_out") or st.get("partner_active") is not True or not st.get("partner_id"): return False
    try:
        return bool(B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1",(int(st["partner_id"]),)).fetchone())
    except Exception:
        log.exception("partner session lookup failed"); return False

def _hard_logout(B,uid):
    old=dict(B.S.get(uid,{}) or {}); keep={k:old[k] for k in ("lang","status","citizenship") if old.get(k) is not None}
    for key in list(old):
        if any(p in key.lower() for p in ("partner","night","irancell","gov_","fida","topup","ticket","chat","service","request","step","mode")): keep.pop(key,None)
    keep.update({"partner_logged_out":True,"partner_active":False,"partner_id":None,"partner":None,"partner_phone":None,"phone":None,"mode":None,"step":None})
    B.S[uid]=keep; return keep

async def _cancel(update,context,B):
    q=update.callback_query; uid=q.from_user.id; st=B.S.setdefault(uid,{})
    lang=st.get("lang","fa")
    if st.get("partner_active") and st.get("partner_id") and not st.get("partner_logged_out"):
        pid=st.get("partner_id"); B.S[uid]={"lang":lang,"status":st.get("status"),"citizenship":st.get("citizenship"),"partner_id":pid,"partner_active":True,"partner_logged_out":False,"mode":"partner","step":"partner"}
        await q.message.reply_text("↩️ به پنل همکاران برگشتید.",reply_markup=B.partner_kb(lang)); return
    B.S[uid]={"lang":lang,"mode":None}; await q.message.reply_text("✅ عملیات لغو شد.",reply_markup=B.main(uid))

async def _dispatch(update,context,B,label):
    q=update.callback_query; uid=q.from_user.id; st=B.S.setdefault(uid,{})
    import telegram_ui_policy_v2 as UI
    fake=UI._fake(update,label)
    if label=="❌ انصراف": return await _cancel(update,context,B)
    if label=="🚪 خروج از پنل":
        _hard_logout(B,uid); await q.message.reply_text("🔒 خروج کامل از پنل همکاران انجام شد.\n\nبرای ورود دوباره باید شماره موبایل و رمز عبور را وارد کنید.",reply_markup=B.main(uid)); return
    if not _partner_ok(B,uid): await q.message.reply_text("⛔ ابتدا با شماره موبایل و رمز عبور وارد پنل همکاران شوید.",reply_markup=B.main(uid)); return
    if label=="💰 موجودی":
        row=B.db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1 LIMIT 1",(int(st["partner_id"]),)).fetchone(); bal=int(row["balance"] or 0) if row else 0
        await q.message.reply_text(f"💰 اعتبار فعلی شما: {bal:,} تومان",reply_markup=B.partner_kb(st.get("lang","fa"))); return
    if label=="💬 ارتباط با مدیریت":
        fn=getattr(UI,"_management_chat",None)
        if fn: await _await_call(fn,update,context,B,q,st)
        else:
            st.update(mode="final_partner_chat",final_chat_partner_id=int(st["partner_id"]))
            await q.message.reply_text("💬 ارتباط با مدیریت فعال شد.\n\nمتن، عکس، فایل، ویس یا ویدیو را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
        return
    if label=="🎫 تیکت به مدیریت":
        try:
            from telegram_business_features import _send_ticket_prompt
            await _await_call(_send_ticket_prompt,fake,B)
        except Exception:
            log.exception("ticket start failed"); await q.message.reply_text("❌ ثبت تیکت با خطا مواجه شد؛ پنل شما حفظ شد.",reply_markup=B.partner_kb(st.get("lang","fa")))
        return
    if label=="📱 حل مشکل سیم کارت ایرانسل":
        try:
            import telegram_irancell_partner_service as IRS
            IRS.PRICE=980_000
            if getattr(IRS,"_ensure_service",None): await _await_call(IRS._ensure_service,B)
            B.db.conn.execute("UPDATE services SET price=?,active=1 WHERE key=?",(980_000,"irancell_sim_issue")); B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",("price_irancell_sim","980000")); B.db.conn.commit()
            st["mode"]="irancell_partner_phone"; st.pop("irancell",None)
            await q.message.reply_text("📱 حل مشکل سیم کارت ایرانسل\n\n📱 شماره موبایل مشترک را وارد کنید:\n\n💰 هزینه خدمت: ۹۸۰٬۰۰۰ تومان\n💳 مبلغ فقط از موجودی همکار کسر می‌شود.",reply_markup=B.cancel_kb(st.get("lang","fa")))
        except Exception:
            try:B.db.conn.rollback()
            except Exception:pass
            log.exception("irancell start failed"); await q.message.reply_text("❌ شروع خدمت ایرانسل با خطا مواجه شد؛ موجودی شما دست‌نخورده باقی ماند.",reply_markup=B.partner_kb(st.get("lang","fa")))
        return
    fn_name=PARTNER_LABELS.get(label)
    if fn_name=="topup":
        fn=getattr(B,"topup",None)
        if fn: await _await_call(fn,fake,context)
        else: st["mode"]="topup_amount"; await q.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
        return
    if fn_name=="gov": await _await_call(getattr(B,"gov",None),fake,context); return
    if fn_name=="sim":
        fn=getattr(B,"sim_start",None)
        if fn: await _await_call(fn,fake,context)
        else: await q.message.reply_text("📱 خدمات سیم کارت در حال حاضر فعال نیست.",reply_markup=B.partner_kb(st.get("lang","fa")))
        return
    if fn_name=="fida": await _await_call(getattr(B,"fida",None),fake,context); return
    if fn_name=="ptrack": await _await_call(getattr(B,"ptrack",None),fake,context); return
    if fn_name=="phistory": await _await_call(getattr(B,"phistory",None),fake,context); return
    try:
        result=UI._dispatch(update,context,B,label)
        if inspect.isawaitable(result): await result; return
        if result is not None: return
    except ApplicationHandlerStop: raise
    except Exception: log.exception("legacy dispatcher failed label=%r",label)
    await q.message.reply_text("❌ این گزینه در حال حاضر قابل اجرا نیست؛ پنل همکاران حفظ شد.",reply_markup=B.partner_kb(st.get("lang","fa")))

def _add_trust_to_main(B):
    old_main=B.main
    def main(uid):
        markup=old_main(uid)
        # Preserve the existing keyboard type. This is critical because some
        # menu builds use ReplyKeyboardMarkup while others use InlineKeyboardMarkup.
        if isinstance(markup,InlineKeyboardMarkup):
            rows=[list(r) for r in markup.inline_keyboard]
            if not any("نماد اعتماد" in str(getattr(b,"text","")) or str(getattr(b,"url",""))==TRUST_URL for r in rows for b in r):
                rows.append([InlineKeyboardButton("🛡️ نماد اعتماد الکترونیکی",url=TRUST_URL)])
                rows.append([InlineKeyboardButton("🌐 وب‌سایت نت یار مهاجر",url=SIZPAY_URL)])
            return InlineKeyboardMarkup(rows)
        return markup
    B.main=main

def install(app,B):
    if getattr(B,"_unified_router_v34",False): return True
    _add_trust_to_main(B)
    async def callback(update,context):
        q=getattr(update,"callback_query",None)
        if not q or not str(q.data or "").startswith("ui2:"): return
        row=B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1",(str(q.data)[4:],)).fetchone()
        if not row:
            try:await q.answer("این دکمه منقضی شده است؛ لطفاً پنل را دوباره باز کنید.",show_alert=True)
            except Exception:pass
            raise ApplicationHandlerStop
        if row["user_id"] and str(row["user_id"])!=str(q.from_user.id): await q.answer("این دکمه متعلق به حساب دیگری است.",show_alert=True); raise ApplicationHandlerStop
        label=str(row["label"] or "").strip()
        if not label: await q.answer("این دکمه دیگر معتبر نیست.",show_alert=True); raise ApplicationHandlerStop
        try:await q.answer()
        except Exception:pass
        st=B.S.setdefault(q.from_user.id,{})
        if row["lang"]:st["lang"]=row["lang"]
        if row["status"]:st["status"]=row["status"]
        try: await _dispatch(update,context,B,label)
        except ApplicationHandlerStop: raise
        except Exception:
            log.exception("unified callback failed label=%r",label)
            safe=B.partner_kb(st.get("lang","fa")) if _partner_ok(B,q.from_user.id) else B.main(q.from_user.id)
            await q.message.reply_text("❌ اجرای گزینه با خطا مواجه شد؛ وضعیت شما حفظ شد. لطفاً دوباره تلاش کنید.",reply_markup=safe)
        raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(callback,pattern=r"^ui2:"),group=-4000000)
    B._unified_router_v34=True; log.info("Unified Telegram callback/session router v34 installed"); return True
