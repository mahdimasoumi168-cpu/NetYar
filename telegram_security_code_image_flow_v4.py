"""Authoritative security-code image workflow for Telegram.

Manager clicks the request's security-code button -> bot asks manager for an
image -> image is sent to the exact partner assigned to that request -> partner
enters the numeric code -> code is returned to the exact manager who initiated
that request. No panel/password credentials are forwarded.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters


def _request(B, rid):
    try:
        return B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1", (int(rid),)).fetchone()
    except Exception:
        return None


def _partner(B, rid, row):
    pid = None
    try:
        cols = {str(x["name"]) for x in B.db.conn.execute("PRAGMA table_info(requests)").fetchall()}
        if "partner_id" in cols:
            x = B.db.conn.execute("SELECT partner_id FROM requests WHERE id=?", (int(rid),)).fetchone()
            if x and x["partner_id"]:
                pid = int(x["partner_id"])
    except Exception:
        pass
    if not pid:
        try:
            x = B.db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1", (int(rid),)).fetchone()
            if x and str(x["answer"] or "").strip().isdigit():
                pid = int(x["answer"])
        except Exception:
            pass
    if not pid:
        try:
            x = str(B.db.setting(f"request_partner_{int(rid)}", "") or "").strip()
            if x.isdigit(): pid = int(x)
        except Exception:
            pass
    if not pid and row is not None:
        try:
            owner = str(row["user_id"] or "").strip()
            if owner.isdigit():
                x = B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(owner),)).fetchone()
                if x: pid = int(x["id"])
        except Exception:
            pass
    if not pid:
        return None, None
    try:
        p = B.db.conn.execute("SELECT id,name,phone FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchone()
    except Exception:
        p = None
    if not p:
        return None, None
    chat = None
    for key in (f"partner_chat_{pid}", f"partner_chat_{p['phone']}"):
        try:
            x = str(B.db.setting(key, "") or "").strip()
            if x.lstrip("-").isdigit():
                chat = int(x); break
        except Exception:
            pass
    if not chat:
        try:
            x = B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=? LIMIT 1", (pid,)).fetchone()
            if x and str(x["telegram_user_id"] or "").strip().lstrip("-").isdigit():
                chat = int(x["telegram_user_id"])
        except Exception:
            pass
    return p, chat


def _admin_kb(rid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده درخواست", callback_data=f"req:v:{rid}")]])


def install(app, B):
    if getattr(B, "_security_code_image_v4", False):
        return True
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS security_code_requests(request_id INTEGER PRIMARY KEY,admin_id INTEGER NOT NULL,partner_id INTEGER NOT NULL,partner_chat INTEGER NOT NULL,image_file_id TEXT DEFAULT '',code TEXT DEFAULT '',status TEXT DEFAULT 'waiting_image',created_at TEXT,updated_at TEXT)")
    B.db.conn.commit()

    async def request_code(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not B.admin(q.from_user.id): return
        data = str(q.data or "").split(":")
        if len(data) != 3 or data[0] != "req" or data[1] != "p": return
        try: rid = int(data[2])
        except Exception: return
        r = _request(B, rid)
        if not r:
            await q.answer("درخواست پیدا نشد", show_alert=True); raise ApplicationHandlerStop
        partner, chat = _partner(B, rid, r)
        if not partner or not chat:
            await q.answer("همکار مرتبط با این درخواست یا حساب تلگرام او پیدا نشد.", show_alert=True); raise ApplicationHandlerStop
        B.db.conn.execute("INSERT OR REPLACE INTO security_code_requests(request_id,admin_id,partner_id,partner_chat,image_file_id,code,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (rid,q.from_user.id,int(partner['id']),int(chat),'','waiting_image', 'waiting_image', B.now(), B.now()))
        B.db.conn.commit()
        st = B.S.setdefault(q.from_user.id, {})
        st.update(security_code_mode="wait_admin_image", security_code_request_id=rid)
        await q.answer()
        await q.message.reply_text(f"🛡 کد امنیتی درخواست {r['tracking_code'] or rid}\n\n📷 حالا تصویر کد امنیتی را همینجا ارسال کنید.\nاین تصویر فقط برای همکار مرتبط با همین درخواست فرستاده می‌شود.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data=f"sec:cancel:{rid}")]]))
        raise ApplicationHandlerStop

    async def admin_image(update, context):
        m = getattr(update, "effective_message", None); u = getattr(update, "effective_user", None)
        if not m or not u or not B.admin(u.id): return
        st = B.S.setdefault(u.id, {})
        if st.get("security_code_mode") != "wait_admin_image": return
        rid = int(st.get("security_code_request_id"))
        row = B.db.conn.execute("SELECT * FROM security_code_requests WHERE request_id=? AND admin_id=? LIMIT 1", (rid,u.id)).fetchone()
        if not row:
            st["security_code_mode"] = None; return
        if not (m.photo or m.document):
            await m.reply_text("❌ لطفاً تصویر کد امنیتی را ارسال کنید."); raise ApplicationHandlerStop
        fid = m.photo[-1].file_id if m.photo else m.document.file_id
        B.db.conn.execute("UPDATE security_code_requests SET image_file_id=?,status='sent_to_partner',updated_at=? WHERE request_id=?", (fid,B.now(),rid)); B.db.conn.commit()
        r = _request(B, rid); chat = int(row["partner_chat"])
        caption = f"🛡 تصویر کد امنیتی\n\n🎫 درخواست: {r['tracking_code'] or rid}\n\nکد داخل تصویر را بخوانید و فقط عدد کد را ارسال کنید."
        try:
            if m.photo:
                await context.bot.send_photo(chat_id=chat, photo=fid, caption=caption)
            else:
                await context.bot.send_document(chat_id=chat, document=fid, caption=caption)
            B.S.setdefault(chat, {}).update(security_code_mode="wait_partner_code", security_code_request_id=rid, security_code_admin_id=u.id)
            await m.reply_text("✅ تصویر کد امنیتی برای همکار مرتبط ارسال شد.\nبعد از ارسال کد، نتیجه مستقیم به مدیریت برمی‌گردد.", reply_markup=_admin_kb(rid))
        except Exception:
            B.db.conn.execute("UPDATE security_code_requests SET status='send_failed',updated_at=? WHERE request_id=?", (B.now(),rid)); B.db.conn.commit()
            await m.reply_text("❌ ارسال تصویر برای همکار انجام نشد.", reply_markup=_admin_kb(rid))
        st["security_code_mode"] = None; st.pop("security_code_request_id",None)
        raise ApplicationHandlerStop

    async def partner_code(update, context):
        m = getattr(update, "effective_message", None); u = getattr(update, "effective_user", None)
        if not m or not u or not getattr(m, "text", None): return
        st = B.S.setdefault(u.id, {})
        if st.get("security_code_mode") != "wait_partner_code": return
        rid = int(st.get("security_code_request_id")); row = B.db.conn.execute("SELECT * FROM security_code_requests WHERE request_id=? LIMIT 1", (rid,)).fetchone()
        if not row or int(row["partner_chat"]) != int(u.id): return
        code = re.sub(r"\D", "", str(m.text or ""))
        if not code:
            await m.reply_text("❌ لطفاً فقط عدد کد امنیتی را ارسال کنید."); raise ApplicationHandlerStop
        if len(code) > 32:
            await m.reply_text("❌ کد امنیتی معتبر نیست."); raise ApplicationHandlerStop
        B.db.conn.execute("UPDATE security_code_requests SET code=?,status='returned_to_admin',updated_at=? WHERE request_id=?", (code,B.now(),rid)); B.db.conn.commit()
        try:
            B.db.answer(rid, "security_code", answer=code)
        except Exception:
            pass
        aid = int(row["admin_id"])
        r = _request(B, rid)
        try:
            await context.bot.send_message(chat_id=aid, text=f"🛡 کد امنیتی دریافت شد\n\n🎫 کد پیگیری: {r['tracking_code'] or rid}\n👥 همکار: {u.effective_user.full_name or u.id}\n🔢 کد امنیتی: {code}\n\nکد مربوط به همان درخواست است.", reply_markup=_admin_kb(rid))
            await m.reply_text("✅ کد امنیتی برای مدیریت ارسال شد.", reply_markup=B.partner_kb())
        except Exception:
            await m.reply_text("❌ ارسال کد برای مدیریت انجام نشد؛ دوباره تلاش کنید.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop
        st["security_code_mode"] = None; st.pop("security_code_request_id",None); st.pop("security_code_admin_id",None)
        raise ApplicationHandlerStop

    async def cancel(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("sec:cancel:"): return
        st=B.S.setdefault(q.from_user.id,{})
        st["security_code_mode"] = None; st.pop("security_code_request_id",None)
        await q.answer(); await q.message.reply_text("❌ درخواست کد امنیتی لغو شد.", reply_markup=B.amenu() if B.admin(q.from_user.id) else B.main(q.from_user.id)); raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cancel, pattern=r"^sec:cancel:"), group=-9000001)
    app.add_handler(CallbackQueryHandler(request_code, pattern=r"^req:p:\d+$"), group=-9000000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, admin_image), group=-8999999)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partner_code), group=-8999998)
    B._security_code_image_v4=True
    return True
