"""Final admin request workflow hardening.

Owns last-mile request controls and sends deterministic status notifications to
other administrators and to the exact Telegram account that created the request.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.request_workflow_final")


def install(app, B):
    if getattr(B, "_request_workflow_final", False):
        return True

    def request(rid):
        try:
            return B.db.conn.execute("SELECT * FROM requests WHERE id=?", (int(rid),)).fetchone()
        except Exception:
            return None

    def owner_id(r):
        for key in ("user_id", "telegram_user_id", "external_id"):
            try:
                value = r[key]
                if value is not None and str(value).strip().lstrip("-").isdigit():
                    return int(value)
            except Exception:
                pass
        return None

    def admin_ids():
        out = set()
        for key in ("ADMIN_IDS", "ADMIN_ID_1", "ADMIN_ID_2", "TELEGRAM_ADMIN_IDS"):
            try:
                raw = __import__("os").getenv(key, "")
                for x in raw.replace(";", ",").replace(" ", ",").split(","):
                    if x.strip().lstrip("-").isdigit(): out.add(int(x.strip()))
            except Exception:
                pass
        for x in getattr(B, "ADM", set()) or set():
            try: out.add(int(x))
            except Exception: pass
        return out

    async def notify_admins(context, actor_id, rid, service, number, action_text):
        text = (
            f"📢 تغییر وضعیت درخواست\n\n"
            f"🧾 خدمت: {service or '-'}\n"
            f"📱 شماره/شناسه: {number or '-'}\n"
            f"🎫 کد پیگیری: {rid}\n"
            f"👤 مدیر انجام‌دهنده: {actor_id}\n"
            f"📌 وضعیت جدید: {action_text}"
        )
        for aid in admin_ids():
            if aid == int(actor_id): continue
            try: await context.bot.send_message(chat_id=aid, text=text)
            except Exception: log.exception("admin notification failed rid=%s aid=%s", rid, aid)

    async def notify_owner(context, r, action_text, extra=""):
        uid = owner_id(r)
        if not uid: return
        text = (
            "📢 وضعیت درخواست شما به‌روزرسانی شد.\n\n"
            f"🧾 خدمت: {r['service_key'] or '-'}\n"
            f"🎫 کد پیگیری: {r['tracking_code'] or r['id']}\n"
            f"📌 وضعیت: {action_text}"
        )
        if extra: text += "\n\n" + extra
        try: await context.bot.send_message(chat_id=uid, text=text)
        except Exception: log.exception("request owner notification failed rid=%s uid=%s", r['id'], uid)

    def partner_for(rid, r):
        pid = None
        try:
            cols = [x["name"] for x in B.db.conn.execute("PRAGMA table_info(requests)").fetchall()]
            if "partner_id" in cols:
                x = B.db.conn.execute("SELECT partner_id FROM requests WHERE id=?", (int(rid),)).fetchone()
                if x and x["partner_id"]: pid = int(x["partner_id"])
        except Exception: pass
        if not pid:
            try:
                x = B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1", (int(rid),)).fetchone()
                if x and str(x["answer"] or "").isdigit(): pid = int(x["answer"])
            except Exception: pass
        if not pid:
            try:
                x = str(B.db.setting(f"request_partner_{rid}", "") or "").strip()
                if x.isdigit(): pid = int(x)
            except Exception: pass
        candidates=[]
        try:
            if pid: candidates=B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1",(pid,)).fetchall()
            if not candidates: candidates=B.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
        except Exception: return None,None
        for p in candidates:
            for key in (f"partner_chat_{p['id']}",f"partner_chat_{p['phone']}"):
                try:
                    chat=str(B.db.setting(key,"") or "").strip()
                    if chat: return p,int(chat)
                except Exception: pass
        return (candidates[0],None) if len(candidates)==1 else (None,None)

    def kb(rid, paid=False, prefix="rq"):
        if prefix == "req":
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
                [InlineKeyboardButton("💰 تأیید دریافت وجه", callback_data=f"req:pay:{rid}"), InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"req:review:{rid}")],
                [InlineKeyboardButton("🔐 درخواست کد از حساب درخواست‌دهنده", callback_data=f"req:c:{rid}")],
                [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}")],
                [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
                [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
            ])
        rows=[[InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"rq:detail:{rid}")],
              [InlineKeyboardButton("📨 درخواست کد از حساب درخواست‌دهنده",callback_data=f"rq:code:{rid}"), InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")]]
        if paid: rows.append([InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"rq:approve:{rid}")])
        else: rows.append([InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"rq:payconfirm:{rid}"),InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"rq:review:{rid}")])
        rows += [[InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")],[InlineKeyboardButton("📌 انتقال به آخر چت",callback_data=f"rq:bottom:{rid}")]]
        return InlineKeyboardMarkup(rows)

    def detail_text(rid,r):
        lines=["📋 اطلاعات کامل درخواست","",f"🎫 کد پیگیری: {r['tracking_code']}",f"🧾 خدمت: {r['service_key']}",f"📌 وضعیت: {r['status']}",f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",f"💳 وضعیت پرداخت: {r['payment_status'] or '-'}",f"💵 روش پرداخت: {r['payment_method'] or '-'}",f"🕐 تاریخ ثبت: {r['created_at'] or '-'}"]
        try:
            for a in B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall():
                v=str(a['answer'] or '').strip()
                if v: lines.append(f"📋 {a['field_key']}: {v}")
                if a['file_id']: lines.append(f"📎 {a['field_key']}: فایل پیوست دارد")
        except Exception: pass
        return "\n".join(lines)

    async def attachments(context,chat_id,rid):
        try: ans=B.db.conn.execute("SELECT field_key,file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",(rid,)).fetchall()
        except Exception: ans=[]
        sent=set()
        for a in ans:
            fid=str(a['file_id'] or '').strip()
            if not fid or fid in sent: continue
            sent.add(fid)
            try: await context.bot.send_photo(chat_id=chat_id,photo=fid,caption=f"📎 {a['field_key']} | درخواست {rid}")
            except Exception:
                try: await context.bot.send_document(chat_id=chat_id,document=fid,caption=f"📎 {a['field_key']} | درخواست {rid}")
                except Exception: log.exception("attachment delivery failed rid=%s",rid)

    async def send_code_request(context,r,code_to_owner=True):
        uid=owner_id(r)
        if not uid: return False
        await context.bot.send_message(chat_id=uid,text=(
            "🔐 درخواست کد\n\n"
            f"🧾 خدمت: {r['service_key'] or '-'}\n"
            f"🎫 کد پیگیری: {r['tracking_code'] or r['id']}\n\n"
            "لطفاً کد موردنیاز این درخواست را همین‌جا ارسال کنید."
        ))
        return True

    async def cb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        data=str(q.data or '')
        if not (data.startswith('rq:') or data.startswith('req:')): return
        parts=data.split(':')
        if len(parts)!=3: return
        prefix,action=parts[0],parts[1]
        try: rid=int(parts[2])
        except Exception: await q.answer('درخواست نامعتبر است',show_alert=True);raise ApplicationHandlerStop
        r=request(rid)
        if not r: await q.answer('درخواست پیدا نشد',show_alert=True);raise ApplicationHandlerStop
        await q.answer()
        paid=str(r['payment_status'] or '').lower()=='paid'
        number='-'
        for key in ('phone','mobile','national_id','tracking_code'):
            try:
                if r[key]: number=r[key]; break
            except Exception: pass

        if action in {'detail','v'}:
            await q.message.reply_text(detail_text(rid,r),reply_markup=kb(rid,paid,prefix)); await attachments(context,q.from_user.id,rid); raise ApplicationHandlerStop
        if action=='bottom':
            await q.message.reply_text('📌 درخواست به انتهای چت منتقل شد.',reply_markup=kb(rid,paid,prefix)); await q.message.reply_text(detail_text(rid,r),reply_markup=kb(rid,paid,prefix)); await attachments(context,q.from_user.id,rid); raise ApplicationHandlerStop
        if action in {'pay','payconfirm'}:
            B.db.conn.execute("UPDATE requests SET payment_status='paid',payment_method='admin_confirmed',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            await notify_admins(context,q.from_user.id,rid,r['service_key'],number,'💰 دریافت وجه تأیید شد')
            await notify_owner(context,r,'💰 دریافت وجه تأیید شد')
            await q.message.reply_text('💰 دریافت وجه تأیید شد. درخواست آماده انجام خدمت است.',reply_markup=kb(rid,True,prefix)); raise ApplicationHandlerStop
        if action=='review':
            B.db.conn.execute("UPDATE requests SET status='reviewing',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            await notify_admins(context,q.from_user.id,rid,r['service_key'],number,'⏳ در حال بررسی')
            await notify_owner(context,r,'⏳ در حال بررسی')
            await q.message.reply_text('⏳ درخواست وارد وضعیت «در حال بررسی» شد.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
        if action in {'a','approve'}:
            if not paid: await q.message.reply_text('⛔ ابتدا دریافت وجه را تأیید کنید.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
            B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            await notify_admins(context,q.from_user.id,rid,r['service_key'],number,'✅ تأیید و انجام شد')
            await notify_owner(context,r,'✅ تأیید و انجام شد','خدمت شما توسط مدیریت انجام و تأیید شد.')
            await q.message.reply_text('✅ درخواست تأیید و انجام شد.',reply_markup=kb(rid,True,prefix)); raise ApplicationHandlerStop
        if action in {'x','reject'}:
            B.db.conn.execute("UPDATE requests SET status='rejected',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            await notify_admins(context,q.from_user.id,rid,r['service_key'],number,'❌ رد شد')
            await notify_owner(context,r,'❌ رد شد','در صورت نیاز می‌توانید با مدیریت پیگیری کنید.')
            await q.message.reply_text('❌ درخواست رد شد.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
        if action in {'c','code'}:
            B.db.conn.execute("UPDATE requests SET status='awaiting_user_code',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            ok=await send_code_request(context,r)
            if not ok: await q.message.reply_text('❌ حساب کاربری درخواست‌دهنده پیدا نشد.',reply_markup=kb(rid,paid,prefix))
            else:
                await notify_admins(context,q.from_user.id,rid,r['service_key'],number,'🔐 درخواست کد از حساب درخواست‌دهنده ارسال شد')
                await q.message.reply_text('📨 درخواست کد دقیقاً برای همان حساب کاربری که این درخواست را ثبت کرده ارسال شد.',reply_markup=kb(rid,paid,prefix))
            raise ApplicationHandlerStop
        if action in {'p','ask'}:
            p,chat=partner_for(rid,r)
            if not p: await q.message.reply_text('❌ هیچ همکار فعالی برای این درخواست پیدا نشد.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
            if not chat: await q.message.reply_text('⚠️ همکار فعال پیدا شد، اما چت او ثبت نشده است.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
            B.db.set_setting(f'request_partner_{rid}',str(p['id']))
            B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            await context.bot.send_message(chat_id=chat,text=f"🔐 درخواست کد از همکار\n🎫 کد پیگیری: {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n\nلطفاً کد موردنیاز این درخواست را ارسال کنید.")
            await notify_admins(context,q.from_user.id,rid,r['service_key'],number,f'🔐 درخواست کد از همکار «{p["name"] or p["phone"]}» ارسال شد')
            await q.message.reply_text(f"📨 درخواست کد برای همکار ارسال شد.\n👤 همکار: {p['name'] or p['phone']}",reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
        if action=='chat':
            p,chat=partner_for(rid,r)
            if not chat: await q.message.reply_text('❌ چت همکار پیدا نشد.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
            await context.bot.send_message(chat_id=chat,text=f"💬 مدیریت برای درخواست {r['tracking_code']} با شما ارتباط برقرار کرد.")
            await q.message.reply_text('💬 ارتباط با همکار فعال شد.',reply_markup=kb(rid,paid,prefix)); raise ApplicationHandlerStop
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cb,pattern=r'^(rq|req):'),group=-60000)
    B._request_workflow_final=True
    log.info('Final admin request workflow installed')
    return True
