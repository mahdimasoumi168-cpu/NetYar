"""Canonical request/payment/reply owner for Telegram.

One owner for customer/admin request actions. It deliberately intercepts only
request callbacks and dedicated reply/payment states, leaving service flows
and the admin menu to their own owners.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop
from payment_invoice import invoice_text

log=logging.getLogger("netyar.canonical_request_flow")

def _request(B,rid):
    try:return B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1",(int(rid),)).fetchone()
    except Exception:return None

def _customer_uid(B,r):
    try:
        x=str(B.db.setting(f"request_chat_{int(r['id'])}","") or "").strip()
        if x.lstrip("-").isdigit(): return int(x)
    except Exception: pass
    try:
        row=B.db.conn.execute("SELECT external_id FROM users WHERE id=? AND platform='telegram' LIMIT 1",(int(r["user_id"]),)).fetchone()
        if row and str(row["external_id"]).lstrip("-").isdigit(): return int(row["external_id"])
    except Exception: pass
    try:
        pid=str(B.db.setting(f"request_partner_{int(r['id'])}","") or "").strip()
        if pid.isdigit():
            x=str(B.db.setting(f"partner_chat_{pid}","") or "").strip()
            if x.lstrip("-").isdigit(): return int(x)
    except Exception: pass
    return None

async def _notify_other_admins(B,context,source_admin,rid,text):
    for aid in list(getattr(B,"ADM",set()) or []):
        try:
            if int(aid)==int(source_admin): continue
            await context.bot.send_message(chat_id=int(aid),text=text)
        except Exception: log.exception("other-admin notification failed rid=%s",rid,aid)

async def _notify_requester(B,context,r,text,with_reply=True):
    target=_customer_uid(B,r)
    if not target:return False
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("💬 پاسخ مجدد",callback_data=f"cust:reply:{int(r['id'])}"),
                               InlineKeyboardButton("❌ انصراف",callback_data=f"cust:reply_cancel:{int(r['id'])}")]]) if with_reply else None
    await context.bot.send_message(chat_id=target,text=text,reply_markup=kb)
    return True

def _has_receipt(B,rid):
    try:
        row=B.db.conn.execute(
            "SELECT 1 FROM request_answers WHERE request_id=? AND field_key IN ('payment_receipt','receipt','payment_proof') AND file_id!='' LIMIT 1",
            (int(rid),),
        ).fetchone()
        return bool(row)
    except Exception:
        return False

def _payment_ready(B,r):
    """A request may proceed only after a real payment state is established.
    Partner requests must already be charged from partner balance. Customer
    card-to-card requests must have a receipt before management can confirm it.
    """
    status=str(r["payment_status"] or "").lower()
    method=str(r["payment_method"] or "").lower()
    if status=="paid":
        return True,"پرداخت قبلاً ثبت شده است."
    if method=="partner_balance":
        return False,"❌ پرداخت این درخواست از اعتبار همکار باید قبل از تأیید خدمت ثبت شده باشد."
    if method=="card_to_card":
        if not _has_receipt(B,r["id"]):
            return False,"❌ رسید پرداخت برای این درخواست ثبت نشده است؛ ابتدا رسید کارت‌به‌کارت را دریافت کنید."
        return True,""
    return False,"❌ روش پرداخت این درخواست مشخص یا تأیید نشده است."

def _buttons(rid,paid=False):
    rows=[
      [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"req:v:{rid}")],
      [InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"req:pay:{rid}"),InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"req:review:{rid}")],
      [InlineKeyboardButton("🔐 درخواست کد از مشترک",callback_data=f"req:c:{rid}")],
      [InlineKeyboardButton("🔐 درخواست کد امنیتی از همکار",callback_data=f"rq:ask:{rid}")],
      [InlineKeyboardButton("✉️ پاسخ به مشترک",callback_data=f"req:r:{rid}")],
      [InlineKeyboardButton("✅ تأیید خدمت",callback_data=f"req:a:{rid}"),InlineKeyboardButton("❌ رد خدمت",callback_data=f"req:x:{rid}")],
      [InlineKeyboardButton("📌 انتقال به آخر چت",callback_data=f"req:bottom:{rid}")],
    ]
    return InlineKeyboardMarkup(rows)

def _answer_lines(B,r):
    lines=[
      "📋 اطلاعات کامل درخواست","",
      f"🎫 کد پیگیری: {r['tracking_code'] or '-'}",
      f"🧾 خدمت: {r['service_key'] or '-'}",
      f"📌 وضعیت: {r['status'] or '-'}",
      f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",
      f"💳 وضعیت پرداخت: {r['payment_status'] or '-'}",
      f"💵 روش پرداخت: {r['payment_method'] or '-'}","",
      "📋 اطلاعات ثبت‌شده:"
    ]
    try:
      rows=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(int(r["id"]),)).fetchall()
      for a in rows:
        v=str(a["answer"] or "").strip()
        if v: lines.append(f"• {a['field_key']}: {v}")
        elif a["file_id"]: lines.append(f"• {a['field_key']}: 📎 فایل پیوست")
    except Exception:pass
    return "\n".join(lines)

async def _admin_reply(update,context,B,rid):
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    r=_request(B,rid)
    if not r:return await update.callback_query.message.reply_text("❌ درخواست پیدا نشد.")
    target=_customer_uid(B,r)
    if not target:return await update.callback_query.message.reply_text("❌ حساب ثبت‌کننده درخواست پیدا نشد.")
    st.update(mode="canonical_admin_reply",canonical_reply_rid=rid,canonical_reply_target=target)
    await update.callback_query.message.reply_text(f"✉️ پاسخ به مشترک\n🎫 {r['tracking_code'] or rid}\n\nمتن پاسخ را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data="req:reply_cancel")]]))
    raise ApplicationHandlerStop

async def _callback(update,context,B):
    q=update.callback_query;d=str(q.data or "")
    if not d.startswith(("req:","panel:","rq:","cust:")):return
    if d=="req:reply_cancel":
        B.S.setdefault(q.from_user.id,{})["mode"]=None
        await q.answer();await q.message.reply_text("❌ پاسخ لغو شد.",reply_markup=B.amenu());raise ApplicationHandlerStop
    if d.startswith("cust:reply:"):
        try:rid=int(d.split(":")[2])
        except Exception:await q.answer("درخواست نامعتبر است",show_alert=True);raise ApplicationHandlerStop
        r=_request(B,rid)
        if not r or _customer_uid(B,r)!=q.from_user.id:
            await q.answer("❌ این درخواست متعلق به این حساب نیست.",show_alert=True);raise ApplicationHandlerStop
        B.S.setdefault(q.from_user.id,{}).update(mode="canonical_customer_reply",canonical_reply_rid=rid)
        await q.answer();await q.message.reply_text(f"💬 پاسخ به مدیریت\n🎫 {r['tracking_code'] or rid}\n\nپیام خود را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data="cust:reply_cancel")]]));raise ApplicationHandlerStop
    if d.startswith("cust:reply_cancel:") or d=="cust:reply_cancel":
        B.S.setdefault(q.from_user.id,{})["mode"]=None;await q.answer();await q.message.reply_text("❌ پاسخ لغو شد.",reply_markup=B.main(q.from_user.id));raise ApplicationHandlerStop
    if not B.admin(q.from_user.id): return
    parts=d.split(":")
    if len(parts)!=3:
        return
    prefix,action,raw=parts
    try:rid=int(raw)
    except Exception:return
    r=_request(B,rid)
    if not r:await q.answer("❌ درخواست پیدا نشد.",show_alert=True);raise ApplicationHandlerStop
    if action=="p":
        # Let the dedicated partner-code owner process legacy req:p callbacks.
        return
    await q.answer()
    if action in {"v","detail"}:
        await q.message.reply_text(_answer_lines(B,r),reply_markup=_buttons(rid,str(r["payment_status"] or "")=="paid"))
        try:
            rows=B.db.conn.execute("SELECT field_key,file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",(rid,)).fetchall()
            for a in rows:
                try:await q.message.reply_document(a["file_id"],caption=f"📎 {a['field_key']}")
                except Exception:
                    try:await q.message.reply_photo(a["file_id"],caption=f"📎 {a['field_key']}")
                    except Exception:pass
        except Exception:pass
        raise ApplicationHandlerStop
    if action in {"r","reply"}:
        return await _admin_reply(update,context,B,rid)
    if action in {"review","a","approve","x","reject","pay","payconfirm","c","bottom","chat"}:
        now=B.now()
        if action in {"pay","payconfirm"}:
            ready,reason=_payment_ready(B,r)
            if not ready:
                await q.message.reply_text(reason,reply_markup=_buttons(rid,False))
                raise ApplicationHandlerStop
            B.db.conn.execute("UPDATE requests SET payment_status='paid',status='submitted',updated_at=? WHERE id=?",(now,rid))
            B.db.conn.commit();msg="✅ دریافت وجه تأیید شد و درخواست آماده ادامه کار است."
        elif action in {"review"}:
            B.db.conn.execute("UPDATE requests SET status='in_review',updated_at=? WHERE id=?",(now,rid));B.db.conn.commit();msg="⏳ درخواست در حال بررسی قرار گرفت."
            await _notify_other_admins(B,context,q.from_user.id,rid,f"🔎 درخواست بررسی شد توسط مدیر دیگر\n\n🎫 {r['tracking_code'] or rid}\n👤 مدیر: {q.from_user.full_name or q.from_user.id}\n📌 وضعیت: در حال بررسی")
            try: await _notify_requester(B,context,r,f"⏳ درخواست شما در حال بررسی است.\n\n🎫 کد پیگیری: {r['tracking_code'] or rid}")
            except Exception: pass
        elif action in {"a","approve"}:
            ready,reason=_payment_ready(B,r)
            if not ready:
                await q.message.reply_text("❌ تا زمانی که پرداخت تأیید نشده باشد، انجام خدمت مجاز نیست.\\n\\n"+reason,reply_markup=_buttons(rid,False))
                raise ApplicationHandlerStop
            B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(now,rid));B.db.conn.commit();msg="✅ درخواست انجام شد."
            try: await _notify_requester(B,context,r,f"✅ درخواست شما تأیید و انجام شد.\n\n🎫 کد پیگیری: {r['tracking_code'] or rid}")
            except Exception: pass
        elif action in {"x","reject"}:
            B.db.conn.execute("UPDATE requests SET status='rejected',updated_at=? WHERE id=?",(now,rid));B.db.conn.commit();msg="❌ درخواست رد شد."
            try: await _notify_requester(B,context,r,f"❌ درخواست شما توسط مدیریت رد شد.\n\n🎫 کد پیگیری: {r['tracking_code'] or rid}")
            except Exception: pass
        elif action=="c":
            target=_customer_uid(B,r)
            if target:
                await context.bot.send_message(chat_id=target,text=f"🔐 مدیریت برای درخواست {r['tracking_code'] or rid} اطلاعات/کد بیشتری لازم دارد.\nلطفاً پاسخ خود را ارسال کنید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 پاسخ به مدیریت",callback_data=f"cust:reply:{rid}")]]))
                B.db.set_setting(f"request_reply_enabled_{rid}","1")
                msg="📨 درخواست پاسخ از مشترک ارسال شد."
            else:msg="❌ حساب مشترک پیدا نشد."
        elif action=="bottom":
            target=_customer_uid(B,r)
            if target:
                try:await context.bot.send_message(chat_id=target,text=f"📌 پیگیری درخواست {r['tracking_code'] or rid}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 پاسخ به مدیریت",callback_data=f"cust:reply:{rid}")]]));msg="📌 درخواست به آخر چت مشترک منتقل شد."
                except Exception:msg="❌ انتقال انجام نشد."
            else:msg="❌ حساب مشترک پیدا نشد."
        else:msg="💬 ارتباط آماده است."
        await q.message.reply_text(msg,reply_markup=_buttons(rid,str(r["payment_status"] or "")=="paid"));raise ApplicationHandlerStop
    return

async def _media(update,context,B):
    msg=update.effective_message;u=update.effective_user
    if not msg or not u:return
    st=B.S.setdefault(u.id,{})
    if st.get("mode")!="invoice_pending":return
    fid=msg.photo[-1].file_id if getattr(msg,"photo",None) else (msg.document.file_id if getattr(msg,"document",None) else "")
    if not fid:return
    rid=st.get("request_id")
    r=_request(B,rid) if rid else None
    if not r:
        st["mode"]=None
        await msg.reply_text("❌ فاکتور معتبر پیدا نشد.",reply_markup=B.main(u.id));raise ApplicationHandlerStop
    B.db.answer(rid,"payment_receipt",file_id=fid)
    B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='pending_review',payment_method='card_to_card',updated_at=? WHERE id=?",(B.now(),int(rid)));B.db.conn.commit()
    try:
        await B.notify_admins(context.application,f"🧾 رسید پرداخت مشترک\n🎫 {r['tracking_code'] or rid}\n💰 مبلغ: {int(r['amount'] or 0):,} تومان\n⚠️ پرداخت منتظر تأیید مدیریت است.",rid)
    except Exception:log.exception("invoice receipt admin notification failed rid=%s",rid)
    st["mode"]=None
    await msg.reply_text(f"✅ رسید پرداخت ارسال شد.\n🎫 کد پیگیری: {r['tracking_code'] or rid}\n⏳ پس از تأیید مدیریت، درخواست انجام می‌شود.",reply_markup=B.main(u.id))
    raise ApplicationHandlerStop

async def _admin_send_any(update,context,B):
    msg=update.effective_message;u=update.effective_user
    if not msg or not u:return
    st=B.S.setdefault(u.id,{})
    if st.get("mode")!="canonical_admin_reply" or not B.admin(u.id):return
    rid=st.get("canonical_reply_rid");target=st.get("canonical_reply_target");r=_request(B,rid) if rid else None
    if not r or not target:
        st["mode"]=None;await msg.reply_text("❌ گیرنده پاسخ پیدا نشد.",reply_markup=B.amenu());raise ApplicationHandlerStop
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("💬 پاسخ مجدد",callback_data=f"cust:reply:{rid}"),InlineKeyboardButton("❌ انصراف",callback_data=f"cust:reply_cancel:{rid}")]])
    try:
        cap=f"✉️ پاسخ مدیریت | {r['tracking_code'] or rid}"
        if msg.text: await context.bot.send_message(chat_id=int(target),text=f"{cap}\n\n{msg.text}",reply_markup=kb)
        elif msg.photo: await context.bot.send_photo(chat_id=int(target),photo=msg.photo[-1].file_id,caption=cap,reply_markup=kb)
        elif msg.document: await context.bot.send_document(chat_id=int(target),document=msg.document.file_id,caption=cap,reply_markup=kb)
        elif msg.voice: await context.bot.send_voice(chat_id=int(target),voice=msg.voice.file_id,caption=cap,reply_markup=kb)
        elif msg.video: await context.bot.send_video(chat_id=int(target),video=msg.video.file_id,caption=cap,reply_markup=kb)
        elif msg.audio: await context.bot.send_audio(chat_id=int(target),audio=msg.audio.file_id,caption=cap,reply_markup=kb)
        else:
            await msg.reply_text("❌ این نوع پیام پشتیبانی نمی‌شود.");raise ApplicationHandlerStop
        st["mode"]=None
        await msg.reply_text("✅ پاسخ برای صاحب درخواست ارسال شد.",reply_markup=B.amenu())
    except ApplicationHandlerStop: raise
    except Exception:
        log.exception("admin reply send failed")
        await msg.reply_text("❌ ارسال پاسخ انجام نشد؛ دوباره تلاش کنید.",reply_markup=B.amenu())
    raise ApplicationHandlerStop

async def _text(update,context,B):
    msg=update.effective_message;u=update.effective_user
    if not msg or not u:return
    st=B.S.setdefault(u.id,{})
    mode=st.get("mode")
    if mode=="canonical_customer_reply" and not B.admin(u.id):
        rid=st.get("canonical_reply_rid");text=str(msg.text or "").strip()
        if not text:return
        r=_request(B,rid)
        if not r or _customer_uid(B,r)!=u.id:
            st["mode"]=None;await msg.reply_text("❌ درخواست معتبر نیست.",reply_markup=B.main(u.id));raise ApplicationHandlerStop
        delivered=0
        for aid in list(getattr(B,"ADM",set()) or []):
            try:
                await context.bot.send_message(chat_id=int(aid),text=f"💬 پاسخ مشترک\n🎫 {r['tracking_code'] or rid}\n\n{text}",reply_markup=_buttons(rid,str(r["payment_status"] or "")=="paid"));delivered+=1
            except Exception:pass
        if delivered:
            st["mode"]=None;await msg.reply_text("✅ پاسخ شما برای مدیریت ارسال شد.",reply_markup=B.main(u.id))
        else:await msg.reply_text("❌ ارسال پاسخ به مدیریت انجام نشد؛ دوباره تلاش کنید.")
        raise ApplicationHandlerStop

app_marker="_canonical_request_flow_v1"
def install(app,B):
    if getattr(B,app_marker,False):return True
    app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B),pattern=r"^(req:|panel:|rq:|cust:)"),group=-110000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.VIDEO | filters.AUDIO,lambda u,c:_admin_send_any(u,c,B)),group=-110001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_admin_send_any(u,c,B)),group=-110001)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,lambda u,c:_media(u,c,B)),group=-110000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_text(u,c,B)),group=-109999)
    setattr(B,app_marker,True)
    log.info("Canonical request/reply owner active")
    return True
