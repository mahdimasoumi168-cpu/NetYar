"""Final request/partner routing guard.

This layer is intentionally last/authoritative:
- entering the partner panel always starts a fresh phone+password login;
- full partner logout invalidates all in-memory authentication state;
- manager replies are routed to the exact Telegram account that created the request;
- manager security-code requests are routed to the exact partner linked to the request;
- partner security codes return to the manager who initiated that request.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.final_request_partner_guard")
PANEL_LABELS = {"👥 پنل همکاران", "👥 Partner panel", "👥 لوحة الشركاء", "پنل همکاران"}
CANCEL_LABELS = {"❌ انصراف", "لغو", "❌ لغو", "❌ Cancel", "❌ إلغاء"}


def _request(B, rid):
    try:
        return B.db.conn.execute("SELECT * FROM requests WHERE id=? LIMIT 1", (int(rid),)).fetchone()
    except Exception:
        return None


def _request_chat(B, rid):
    try:
        import request_language_actions as L
        x = L.request_chat(B.db, int(rid))
        if x and str(x).strip().lstrip("-").isdigit():
            return int(x)
    except Exception:
        pass
    try:
        x = str(B.db.setting(f"request_chat_{int(rid)}", "") or "").strip()
        return int(x) if x.lstrip("-").isdigit() else None
    except Exception:
        return None


def _partner_for(B, rid, row):
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
    candidates = []
    try:
        if pid:
            candidates = B.db.conn.execute("SELECT id,name,phone FROM partners WHERE id=? AND active=1 LIMIT 1", (pid,)).fetchall()
        if not candidates and row is not None:
            owner = str(row["user_id"] or "").strip()
            if owner.isdigit():
                candidates = B.db.conn.execute("SELECT id,name,phone FROM partners WHERE id=? AND active=1 LIMIT 1", (int(owner),)).fetchall()
    except Exception:
        pass
    for p in candidates:
        for key in (f"partner_chat_{p['id']}", f"partner_chat_{p['phone']}"):
            try:
                x = str(B.db.setting(key, "") or "").strip()
                if x and x.lstrip("-").isdigit(): return p, int(x)
            except Exception:
                pass
        try:
            x = B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=? LIMIT 1", (int(p["id"]),)).fetchone()
            if x and str(x["telegram_user_id"] or "").strip().isdigit(): return p, int(x["telegram_user_id"])
        except Exception:
            pass
    return (candidates[0], None) if candidates else (None, None)


def _full_request_text(B, rid):
    r = _request(B, rid)
    if not r: return None
    try:
        import request_language_actions as L
        lang = L.request_language(B.db, rid); label = lambda k: L.field_label(k, lang); service = L.service_name(r["service_key"], lang)
    except Exception:
        label = lambda k: f"📋 {k}"; service = str(r["service_key"] or "-")
    chat = _request_chat(B, rid)
    lines = ["📋 اطلاعات کامل درخواست", "", f"🎫 کد پیگیری: {r['tracking_code'] or '-'}", f"🧾 خدمت: {service}", f"👤 حساب ثبت‌کننده: {chat or r['user_id']}", f"📌 وضعیت: {r['status'] or '-'}", f"💰 مبلغ: {int(r['amount'] or 0):,} تومان", f"💳 وضعیت پرداخت: {r['payment_status'] or '-'}"]
    if r["payment_method"]: lines.append(f"💵 روش پرداخت: {r['payment_method']}")
    if r["created_at"]: lines.append(f"🕐 زمان ثبت: {r['created_at']}")
    for k in r.keys():
        if k in {"id","tracking_code","service_key","status","amount","payment_status","payment_method","created_at","updated_at","language"}: continue
        v = str(r[k] or "").strip()
        if v: lines.append(f"{label(k)}: {v}")
    lines += ["", "📋 اطلاعات و مدارک ثبت‌شده:"]
    files = []
    try:
        rows = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
        for a in rows:
            k = str(a["field_key"] or ""); v = str(a["answer"] or "").strip(); fid = str(a["file_id"] or "").strip()
            if v: lines.append(f"{label(k)}: {v}")
            if fid:
                lines.append(f"{label(k)}: 📎 پیوست شده")
                files.append((k, fid))
    except Exception:
        pass
    return "\n".join(lines), files


def _admin_request_kb(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
        [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}")],
        [InlineKeyboardButton("⏳ بررسی اولیه", callback_data=f"req:review:{rid}")],
        [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
        [InlineKeyboardButton("✉️ پاسخ به مشترک/همکار", callback_data=f"req:r:{rid}")],
    ])


def install(app, B):
    if getattr(B, "_final_request_partner_guard_v1", False): return True

    # Mandatory fresh partner authentication for both callback and text entry.
    async def panel_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("ui2:"): return
        token = str(q.data)[4:]
        row = B.db.conn.execute("SELECT label FROM ui2_callbacks WHERE token=? AND user_id=? LIMIT 1", (token, str(q.from_user.id))).fetchone()
        label = str(row["label"] or "").strip() if row else ""
        if label not in PANEL_LABELS: return
        uid = q.from_user.id; st = B.S.setdefault(uid, {})
        try:
            from telegram_offhours_partner_gate_v2 import _is_open, _allowed_during_closed, _closed_text, _closed_markup
            if not _is_open(B) and not _allowed_during_closed(B, uid):
                await q.answer("❌ خارج از ساعت کاری است.", show_alert=True)
                await q.message.reply_text(_closed_text(B), reply_markup=_closed_markup())
                raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            pass
        # A panel entry is always a new authentication transaction.
        for k in ("partner_id","partner_active","partner_phone","partner","phone","partner_logged_out","partner_gate_mode","partner_registration","mode","step"):
            st.pop(k, None)
        st["partner_gate_mode"] = "phone"
        st["partner_registration"] = {}
        st["lang"] = "fa"
        await q.answer()
        await q.message.reply_text("👥 ورود به پنل همکاران\n\n📱 شماره موبایل همکار را وارد کنید:", reply_markup=B.cancel_kb("fa"))
        raise ApplicationHandlerStop

    async def panel_text(update, context):
        msg = getattr(update, "effective_message", None); u = getattr(update, "effective_user", None)
        if not msg or not u or str(getattr(msg, "text", "") or "").strip() not in PANEL_LABELS: return
        uid = u.id; st = B.S.setdefault(uid, {})
        try:
            from telegram_offhours_partner_gate_v2 import _is_open, _allowed_during_closed, _closed_text, _closed_markup
            if not _is_open(B) and not _allowed_during_closed(B, uid):
                await msg.reply_text(_closed_text(B), reply_markup=_closed_markup())
                raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception:
            pass
        for k in ("partner_id","partner_active","partner_phone","partner","phone","partner_logged_out","partner_gate_mode","partner_registration","mode","step"):
            st.pop(k, None)
        st["partner_gate_mode"] = "phone"; st["partner_registration"] = {}; st["lang"] = "fa"
        await msg.reply_text("👥 ورود به پنل همکاران\n\n📱 شماره موبایل همکار را وارد کنید:", reply_markup=B.cancel_kb("fa"))
        raise ApplicationHandlerStop

    # Manager -> exact requester/partner reply flow.
    async def request_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not B.admin(q.from_user.id): return
        data = str(q.data or ""); parts = data.split(":")
        if len(parts) != 3 or parts[0] != "req" or parts[1] not in {"r","p","v","a","x","review"}: return
        try: rid = int(parts[2])
        except Exception: return
        r = _request(B, rid)
        if not r:
            await q.answer("درخواست پیدا نشد", show_alert=True); raise ApplicationHandlerStop
        action = parts[1]
        if action == "p":
            partner, chat = _partner_for(B, rid, r)
            if not partner or not chat:
                await q.answer("همکار مرتبط با این درخواست یا چت او پیدا نشد.", show_alert=True); raise ApplicationHandlerStop
            B.db.set_setting(f"request_partner_{rid}", str(partner["id"]))
            B.db.set_setting(f"partner_code_request_admin_{rid}", str(q.from_user.id))
            B.db.set_setting(f"request_code_chat_{rid}", str(chat))
            B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            st = B.S.setdefault(chat, {}); st.update(mode="final_partner_code", final_code_request_rid=rid, final_code_admin=str(q.from_user.id), lang="fa")
            await q.answer("برای همکار ارسال شد")
            await context.bot.send_message(chat_id=chat, text=f"🔐 درخواست کد از مدیریت\n\n🎫 کد پیگیری: {r['tracking_code'] or rid}\n🧾 خدمت: {r['service_key'] or '-'}\n\nلطفاً کد موردنیاز این درخواست را فقط در همین چت ارسال کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data=f"finalcode:cancel:{rid}")]]))
            await q.message.reply_text(f"📨 درخواست کد برای همکار «{partner['name'] or partner['phone']}» ارسال شد.", reply_markup=_admin_request_kb(rid)); raise ApplicationHandlerStop
        if action == "r":
            chat = _request_chat(B, rid)
            if not chat:
                await q.answer("حساب ثبت‌کننده این درخواست مشخص نیست.", show_alert=True); raise ApplicationHandlerStop
            st = B.S.setdefault(q.from_user.id, {}); st.update(mode="final_request_reply", final_request_reply_rid=rid, final_request_reply_chat=chat)
            await q.answer()
            await q.message.reply_text("✉️ متن پاسخ را برای همین درخواست ارسال کنید.\n\nپیام مستقیماً برای همان حسابی می‌رود که این درخواست را ثبت کرده است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data=f"finalreply:cancel:{rid}")]])); raise ApplicationHandlerStop
        if action == "v":
            payload = _full_request_text(B, rid); text, files = payload
            await q.answer(); await q.message.reply_text(text, reply_markup=_admin_request_kb(rid))
            for key, fid in files:
                try: await context.bot.send_photo(chat_id=q.from_user.id, photo=fid, caption=f"📎 {key} | {r['tracking_code'] or rid}")
                except Exception:
                    try: await context.bot.send_document(chat_id=q.from_user.id, document=fid, caption=f"📎 {key} | {r['tracking_code'] or rid}")
                    except Exception: pass
            raise ApplicationHandlerStop
        if action in {"a","x","review"}:
            status = {"a":"completed","x":"rejected","review":"reviewing"}[action]
            B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (status, B.now(), rid)); B.db.conn.commit()
            chat = _request_chat(B, rid)
            if chat:
                text = {"a":"✅ درخواست شما انجام شد.","x":"❌ درخواست شما رد شد.","review":"⏳ درخواست شما وارد بررسی شد."}[action]
                try: await context.bot.send_message(chat_id=chat, text=f"🎫 {r['tracking_code'] or rid}\n\n{text}")
                except Exception: pass
            await q.answer(); await q.message.reply_text({"a":"✅ درخواست تأیید و انجام شد.","x":"❌ درخواست رد شد.","review":"⏳ درخواست وارد بررسی اولیه شد."}[action], reply_markup=_admin_request_kb(rid)); raise ApplicationHandlerStop

    async def admin_reply_text(update, context):
        msg = getattr(update, "effective_message", None); u = getattr(update, "effective_user", None)
        if not msg or not u or not getattr(msg, "text", None): return
        st = B.S.setdefault(u.id, {})
        if st.get("mode") != "final_request_reply" or not st.get("final_request_reply_rid"): return
        if str(msg.text).strip() in CANCEL_LABELS:
            st.pop("final_request_reply_rid", None); st.pop("final_request_reply_chat", None); st["mode"] = None; await msg.reply_text("✅ پاسخ لغو شد.", reply_markup=B.amenu()); raise ApplicationHandlerStop
        rid = int(st["final_request_reply_rid"]); chat = int(st.get("final_request_reply_chat") or 0)
        if not chat:
            st["mode"] = None; await msg.reply_text("❌ مقصد این درخواست مشخص نیست.", reply_markup=B.amenu()); raise ApplicationHandlerStop
        r = _request(B, rid); text = msg.text.strip()
        try:
            await context.bot.send_message(chat_id=chat, text=f"💬 پاسخ مدیریت\n\n🎫 {r['tracking_code'] if r else rid}\n\n{text}")
            await msg.reply_text("✅ پاسخ برای همان حساب ثبت‌کننده درخواست ارسال شد.", reply_markup=B.amenu())
        except Exception:
            await msg.reply_text("❌ ارسال پاسخ انجام نشد؛ مقصد درخواست تغییر نکرده است.", reply_markup=B.amenu())
        st.pop("final_request_reply_rid", None); st.pop("final_request_reply_chat", None); st["mode"] = None
        raise ApplicationHandlerStop

    async def partner_code_text(update, context):
        msg = getattr(update, "effective_message", None); u = getattr(update, "effective_user", None)
        if not msg or not u or not getattr(msg, "text", None): return
        st = B.S.setdefault(u.id, {})
        if st.get("mode") != "final_partner_code" or not st.get("final_code_request_rid"): return
        text = str(msg.text).strip()
        if not text or text in CANCEL_LABELS: return
        rid = int(st["final_code_request_rid"]); r = _request(B, rid)
        if not r:
            st["mode"] = None; return
        aid = str(st.get("final_code_admin") or B.db.setting(f"partner_code_request_admin_{rid}", "") or "").strip()
        if not aid.isdigit():
            await msg.reply_text("❌ مدیریتِ درخواست مشخص نیست."); raise ApplicationHandlerStop
        try:
            B.db.answer(rid, "partner_code", answer=text)
            B.db.conn.execute("UPDATE requests SET status='processing',updated_at=? WHERE id=?", (B.now(), rid)); B.db.conn.commit()
            payload = _full_request_text(B, rid); full = payload[0] if payload else ""
            out = f"🔐 کد همکار دریافت شد\n\n🎫 {r['tracking_code'] or rid}\n\n{full}\n\n🔑 کد امنیتی: {text}"
            await context.bot.send_message(chat_id=int(aid), text=out, reply_markup=_admin_request_kb(rid))
            await msg.reply_text("✅ کد برای مدیریت ارسال شد.", reply_markup=B.partner_kb())
        except Exception:
            await msg.reply_text("❌ ارسال کد برای مدیریت انجام نشد؛ دوباره تلاش کنید.", reply_markup=B.partner_kb())
            raise ApplicationHandlerStop
        st.pop("final_code_request_rid", None); st.pop("final_code_admin", None); st["mode"] = None
        B.db.set_setting(f"partner_code_request_admin_{rid}", ""); B.db.set_setting(f"request_code_chat_{rid}", "")
        raise ApplicationHandlerStop

    async def final_cancel(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("final"):
            return
        uid = q.from_user.id; st = B.S.setdefault(uid, {})
        st["mode"] = None
        for k in ("final_code_request_rid","final_code_admin","final_request_reply_rid","final_request_reply_chat"): st.pop(k, None)
        await q.answer(); await q.message.reply_text("✅ عملیات لغو شد.", reply_markup=B.main(uid)); raise ApplicationHandlerStop

    async def hard_logout(update, context):
        uid = update.effective_user.id; st = B.S.setdefault(uid, {})
        lang = st.get("lang", "fa"); status = st.get("status") or st.get("citizenship")
        B.S[uid] = {"lang": lang, "partner_logged_out": True, "mode": None}
        if status: B.S[uid].update(status=status, citizenship=status)
        await update.effective_message.reply_text("🔒 خروج کامل از پنل همکاران انجام شد.\n\nبرای ورود دوباره باید شماره موبایل و رمز عبور را دوباره وارد کنید.", reply_markup=B.main(uid))

    # Install before legacy callback owners. Text entry is also early, but the
    # off-hours check above prevents bypassing the night gate.
    app.add_handler(CallbackQueryHandler(panel_callback, pattern=r"^ui2:"), group=-8000000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, panel_text), group=-7999999)
    app.add_handler(CallbackQueryHandler(final_cancel, pattern=r"^final(?:reply|code):"), group=-7999998)
    app.add_handler(CallbackQueryHandler(request_callback, pattern=r"^req:(?:r|p|v|a|x|review):\d+$"), group=-7999997)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply_text), group=-7999996)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partner_code_text), group=-7999995)
    B.partner_exit = hard_logout
    B._final_request_partner_guard_v1 = True
    log.info("Final request/partner routing guard v1 installed")
    return True
