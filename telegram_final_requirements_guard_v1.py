"""Final Telegram requirements guard."""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
log = logging.getLogger("netyar.telegram.final_requirements_guard_v1")
PARTNER_LABELS={"👥 پنل همکاران","👥 Partner panel","👥 لوحة الشركاء"}
LOGOUT_LABELS={"🚪 خروج از پنل","🚪 Exit panel","🔒 خروج دائمی","🔒 Permanent logout","🔒 تسجيل الخروج الدائم"}


def _hard_logout(B,uid):
    st=dict(B.S.get(uid,{}) or {})
    keep={k:st[k] for k in ("lang","status","citizenship") if st.get(k) is not None}
    keep.update({"partner_logged_out":True,"partner_active":False,"partner_id":None,"mode":None,"step":None})
    B.S[uid]=keep
    try:
        B.db.conn.execute("DELETE FROM partner_telegram_links WHERE telegram_user_id=?",(str(uid),));B.db.conn.commit()
    except Exception: pass
    return keep


def _request_row(B,rid):
    try:return B.db.conn.execute("SELECT * FROM requests WHERE id=?",(int(rid),)).fetchone()
    except Exception:return None


def _requester_chat(B,row):
    if not row:return None
    try:
        u=B.db.conn.execute("SELECT platform,external_id FROM users WHERE id=?",(row["user_id"],)).fetchone()
        if u and str(u["platform"]).lower()=="telegram" and str(u["external_id"]).isdigit():return int(u["external_id"])
    except Exception:pass
    try:
        l=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(int(row["user_id"]),)).fetchone()
        if l and str(l["telegram_user_id"]).isdigit():return int(l["telegram_user_id"])
    except Exception:pass
    return None


def _partner_id(B,row):
    if not row:return None
    try:
        a=B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(row["id"],)).fetchone()
        if a and str(a["answer"] or "").strip().isdigit():return int(a["answer"])
    except Exception:pass
    try:
        p=B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1",(row["user_id"],)).fetchone()
        if p:return int(p["id"])
    except Exception:pass
    return None


def _partner_chat(B,pid):
    if not pid:return None
    try:
        r=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(int(pid),)).fetchone()
        if r and str(r["telegram_user_id"]).isdigit():return int(r["telegram_user_id"])
    except Exception:pass
    try:
        v=B.db.setting(f"partner_chat_{pid}","")
        if str(v).isdigit():return int(v)
    except Exception:pass
    return None


def _controls(rid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده درخواست",callback_data=f"req:v:{rid}")],[InlineKeyboardButton("🔐 درخواست کد از همکار",callback_data=f"req:p:{rid}")],[InlineKeyboardButton("✅ تأیید",callback_data=f"req:a:{rid}"),InlineKeyboardButton("❌ رد",callback_data=f"req:x:{rid}")]])


async def _notify_requester(B,context,row,text):
    chat=_requester_chat(B,row)
    if not chat:return False
    try:await context.bot.send_message(chat_id=chat,text=text);return True
    except Exception:log.exception("requester notification failed for request %s",row["id"]);return False


async def _admin_request_callback(update,context,B):
    q=update.callback_query
    if not q or not B.admin(q.from_user.id):return
    data=(q.data or "").split(":")
    if len(data)!=3 or data[0] not in {"req","rq"}:return
    action=data[1]
    allowed=(data[0]=="req" and action in {"a","x","p"}) or (data[0]=="rq" and action in {"approve","reject","ask"})
    # Let the existing full-details/payment routers keep ownership of their
    # callbacks; this guard only owns delivery-sensitive actions.
    if not allowed:return
    try:rid=int(data[2])
    except Exception:await q.answer("درخواست نامعتبر",show_alert=True);return
    row=_request_row(B,rid)
    if not row:await q.answer("درخواست پیدا نشد",show_alert=True);return
    await q.answer()
    if data[0]=="req" and action in {"a","x"}:
        status="approved" if action=="a" else "rejected"
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid));B.db.conn.commit()
        ok=await _notify_requester(B,context,row,"✅ درخواست شما توسط مدیریت تأیید شد." if status=="approved" else "❌ درخواست شما توسط مدیریت رد شد.")
        try:await q.message.edit_reply_markup(reply_markup=None)
        except Exception:pass
        return await q.message.reply_text("✅ تأیید شد و نتیجه برای همان درخواست‌دهنده ارسال شد." if ok else "⚠️ وضعیت ثبت شد، اما حساب درخواست‌دهنده برای ارسال پیام پیدا نشد.")
    if data[0]=="rq" and action in {"approve","reject"}:
        if action=="approve" and str(row["payment_status"] or "").lower()!="paid":return await q.message.reply_text("⛔ ابتدا دریافت وجه را تأیید کنید.")
        status="completed" if action=="approve" else "rejected"
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,B.now(),rid));B.db.conn.commit()
        ok=await _notify_requester(B,context,row,"✅ خدمت شما انجام شد و درخواست بسته شد." if status=="completed" else "❌ درخواست شما توسط مدیریت رد شد.")
        return await q.message.reply_text("نتیجه برای همان ثبت‌کننده ارسال شد." if ok else "⚠️ وضعیت ثبت شد، اما ارسال به ثبت‌کننده ممکن نشد.")
    if action in {"p","ask"}:
        pid=_partner_id(B,row);target=_partner_chat(B,pid)
        if not target:return await q.message.reply_text("⚠️ همکار متصل به همین درخواست پیدا نشد؛ درخواست به فرد دیگری ارسال نمی‌شود.")
        await context.bot.send_message(chat_id=target,text=f"🔐 درخواست کد از همکار\n🎫 کد پیگیری: {row['tracking_code']}\n\nمدیریت برای همین درخواست کد می‌خواهد. لطفاً کد خدمت را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📨 ارسال کد",callback_data=f"rqcode:send:{rid}:1")]]))
        return await q.message.reply_text("✅ درخواست کد فقط برای همکار ثبت‌شده در همین درخواست ارسال شد.")


async def _partner_entry(update,context,B):
    if not update.message or (update.message.text or "").strip() not in PARTNER_LABELS:return
    uid=update.effective_user.id;st=_hard_logout(B,uid);st["mode"]="p_phone";st["step"]="partner_phone"
    await update.message.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))


async def _logout(update,context,B):
    if not update.message or (update.message.text or "").strip() not in LOGOUT_LABELS:return
    uid=update.effective_user.id;_hard_logout(B,uid)
    await update.message.reply_text("🔒 خروج کامل انجام شد. برای ورود دوباره به پنل همکاران باید اطلاعات ورود را از ابتدا وارد کنید.",reply_markup=B.main(uid))


def _wrap_notify(B):
    if getattr(B,"_final_requirements_notify_v1",False):return
    async def notify(app,message,request_id=None,inline=None,files=None):
        if not B.ADM:return
        ids=list(files or [])
        if request_id:
            try:ids.extend(r["file_id"] for r in B.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id<>'' ORDER BY id",(int(request_id),)).fetchall() if r["file_id"])
            except Exception:log.exception("request attachment lookup failed")
        markup=_controls(request_id) if request_id else inline
        for aid in B.ADM:
            try:
                await app.bot.send_message(chat_id=int(aid),text=message,reply_markup=markup)
                for fid in dict.fromkeys(ids):
                    try:await app.bot.send_photo(chat_id=int(aid),photo=fid,caption=f"📎 مدرک درخواست #{request_id}")
                    except Exception:await app.bot.send_document(chat_id=int(aid),document=fid,caption=f"📎 مدرک درخواست #{request_id}")
            except Exception:log.exception("complete admin request notification failed")
    B.notify_admins=notify;B._final_requirements_notify_v1=True


def install(app,B):
    if getattr(B,"_final_requirements_guard_v1",False):return
    _wrap_notify(B)
    app.add_handler(CallbackQueryHandler(lambda u,c:_admin_request_callback(u,c,B),pattern=r"^(req|rq):"),group=-200000)
    app.add_handler(MessageHandler(filters.Regex(r"^(👥 پنل همکاران|👥 Partner panel|👥 لوحة الشركاء)$"),lambda u,c:_partner_entry(u,c,B)),group=-200000)
    app.add_handler(MessageHandler(filters.Regex(r"^(🚪 خروج از پنل|🚪 Exit panel|🔒 خروج دائمی|🔒 Permanent logout|🔒 تسجيل الخروج الدائم)$"),lambda u,c:_logout(u,c,B)),group=-199999)
    B._final_requirements_guard_v1=True;log.info("FINAL requirements guard v1 installed")
