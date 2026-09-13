"""Final Telegram operations overlay for NetYar.
Adds complete request controls, partner code/captcha/checkup relay, chat relay,
request re-posting, and strict night-worker access without changing payment flow.
"""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.final_ops_overlay")
MAX_ROUNDS = 10

def install(app, B):
    if getattr(B, "_final_ops_overlay_v1", False):
        return True

    def buttons(rid):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 مشاهده اطلاعات کامل", callback_data=f"req:v:{rid}")],
            [InlineKeyboardButton("✅ تأیید خدمت", callback_data=f"req:a:{rid}"), InlineKeyboardButton("❌ رد خدمت", callback_data=f"req:x:{rid}")],
            [InlineKeyboardButton("🔐 درخواست کد از همکار", callback_data=f"req:p:{rid}"), InlineKeyboardButton("🔐 درخواست کد", callback_data=f"panel:askcode:{rid}")],
            [InlineKeyboardButton("🧩 درخواست کپچا", callback_data=f"req:captcha:{rid}"), InlineKeyboardButton("📝 درخواست نوشتار چکاپ", callback_data=f"req:checkup:{rid}")],
            [InlineKeyboardButton("💬 ارتباط با همکار", callback_data=f"req:chat:{rid}"), InlineKeyboardButton("📌 انتقال به آخر چت", callback_data=f"req:bottom:{rid}")],
            [InlineKeyboardButton("✉️ پاسخ", callback_data=f"req:r:{rid}")],
        ])

    def partner_for(rid):
        try:
            r = B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if not r: return None, None
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (r["user_id"],)).fetchone()
            if p: return r, p
            mapped = B.db.setting(f"request_partner_{rid}", "")
            if mapped.isdigit():
                p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (int(mapped),)).fetchone()
                if p: return r, p
            return r, None
        except Exception:
            log.exception("partner lookup")
            return None, None

    def partner_chat(pid, phone=None):
        for key in (f"partner_chat_{pid}", f"partner_chat_{phone}" if phone else ""):
            if not key: continue
            value = B.db.setting(key, "")
            try:
                if value: return int(value)
            except Exception: pass
        return None

    async def send_to_admin(context, admin_id, text, rid=None):
        try:
            await context.bot.send_message(chat_id=int(admin_id), text=text, reply_markup=buttons(rid) if rid else None)
            return True
        except Exception:
            log.exception("admin relay failed")
            return False

    async def admin_cb(update, context):
        q = update.callback_query
        if not q or not B.admin(q.from_user.id): return
        data = str(q.data or "")
        if not (data.startswith("req:") or data.startswith("panel:askcode:")):
            return
        parts = data.split(":")
        rid = None
        if data.startswith("panel:askcode:"):
            rid = int(parts[2]); action = "code"
        else:
            if len(parts) < 3: return
            try: rid = int(parts[2])
            except Exception: return
            action = parts[1]
        r, p = partner_for(rid)
        if not r:
            await q.answer("درخواست پیدا نشد", show_alert=True); raise ApplicationHandlerStop
        if action in {"a", "x", "review", "payconfirm"}:
            return
        if not p:
            await q.answer("همکار این درخواست مشخص نیست", show_alert=True); raise ApplicationHandlerStop
        chat = partner_chat(p["id"], p["phone"])
        if not chat:
            await q.answer("همکار هنوز چت خود را به پنل وصل نکرده است", show_alert=True); raise ApplicationHandlerStop

        if action in {"p", "code"}:
            key=f"final_code_round_{rid}"; n=int(B.db.setting(key,"0") or 0)
            if n >= MAX_ROUNDS:
                await q.answer("سقف ۱۰ درخواست کد تکمیل شده است", show_alert=True); raise ApplicationHandlerStop
            n += 1; B.db.set_setting(key,str(n)); B.db.set_setting(f"final_relay_{chat}",f"code|{rid}|{q.from_user.id}")
            B.db.set_setting(f"partner_code_request_{p['id']}",f"{rid}|{r['tracking_code']}")
            B.db.set_setting(f"partner_code_request_admin_{rid}",str(q.from_user.id))
            B.db.conn.execute("UPDATE requests SET status='awaiting_partner_code',updated_at=? WHERE id=?",(B.now(),rid)); B.db.conn.commit()
            B.S.setdefault(chat,{})["partner_id"]=p["id"]
            B.S[chat]["mode"]="partner_send_code"; B.S[chat]["code_request_rid"]=rid
            await context.bot.send_message(chat_id=chat,text=f"🔐 درخواست کد خدمت\n🎫 {r['tracking_code']}\n🧾 {r['service_key']}\n\nلطفاً کد را ارسال کنید.\n🔁 نوبت {n} از {MAX_ROUNDS}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو",callback_data=f"finalrelay:cancel:{rid}")]]))
            await q.answer(f"درخواست کد نوبت {n} ارسال شد")
            raise ApplicationHandlerStop

        if action == "captcha":
            B.db.set_setting(f"final_relay_{q.from_user.id}",f"captcha|{rid}|{chat}")
            B.db.set_setting(f"final_relay_target_{chat}",f"captcha|{rid}|{q.from_user.id}")
            B.S.setdefault(chat,{})["partner_id"]=p["id"]
            B.S[chat]["mode"]="final_partner_captcha"; B.S[chat]["final_relay_rid"]=rid; B.S[chat]["final_relay_admin"]=q.from_user.id
            await q.message.reply_text("🧩 درخواست کپچا\n\nلطفاً تصویر کپچا را همین‌جا برای ربات ارسال کنید تا برای همکار مربوط به این درخواست فرستاده شود.")
            await q.answer("تصویر کپچا را ارسال کنید")
            raise ApplicationHandlerStop

        if action == "checkup":
            B.db.set_setting(f"final_relay_{q.from_user.id}",f"checkup|{rid}|{chat}")
            B.db.set_setting(f"final_relay_target_{chat}",f"checkup|{rid}|{q.from_user.id}")
            B.S.setdefault(chat,{})["partner_id"]=p["id"]
            B.S[chat]["mode"]="final_partner_checkup"; B.S[chat]["final_relay_rid"]=rid; B.S[chat]["final_relay_admin"]=q.from_user.id
            await q.answer("متن درخواست چکاپ را برای ربات ارسال کنید", show_alert=True)
            await q.message.reply_text("📝 متن چکاپ را ارسال کنید تا برای همکار مربوطه فرستاده شود.")
            raise ApplicationHandlerStop

        if action == "chat":
            B.S.setdefault(q.from_user.id,{})["mode"]="final_admin_chat"; B.S[q.from_user.id]["final_chat_partner"]=chat
            B.S.setdefault(chat,{})["mode"]="final_partner_chat"; B.S[chat]["final_chat_admin"]=q.from_user.id
            await q.message.reply_text("💬 ارتباط با همکار فعال شد. پیام متنی، عکس یا صوت خود را ارسال کنید.",reply_markup=B.amenu())
            await context.bot.send_message(chat_id=chat,text="💬 مدیریت ارتباط با شما را آغاز کرد. هر پیام متنی، عکس یا صوتی که ارسال کنید به مدیریت برمی‌گردد.",reply_markup=B.partner_kb())
            await q.answer(); raise ApplicationHandlerStop

        if action == "bottom":
            files=[]
            try:
                rows=B.db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id!='' ORDER BY id",(rid,)).fetchall(); files=[x["file_id"] for x in rows]
            except Exception: pass
            await q.message.reply_text(f"📌 درخواست #{r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n\nدرخواست دوباره در انتهای چت ارسال شد.",reply_markup=buttons(rid))
            for fid in dict.fromkeys(files):
                try: await context.bot.send_photo(chat_id=q.from_user.id,photo=fid,caption=f"📎 فایل درخواست {r['tracking_code']}")
                except Exception: pass
            await q.answer("درخواست به انتهای چت منتقل شد"); raise ApplicationHandlerStop

        if action == "v":
            rows=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
            lines=[f"📋 اطلاعات کامل درخواست\n🎫 {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}"]
            for x in rows:
                if x["answer"]: lines.append(f"• {x['field_key']}: {x['answer']}")
                elif x["file_id"]: lines.append(f"• {x['field_key']}: 📎 فایل پیوست")
            await q.message.reply_text("\n".join(lines),reply_markup=buttons(rid)); await q.answer(); raise ApplicationHandlerStop

    async def relay_admin_media(update, context):
        uid=update.effective_user.id; spec=B.db.setting(f"final_relay_{uid}","")
        if not spec: return
        kind,rid,chat=spec.split("|",2); rid=int(rid); chat=int(chat)
        msg=update.effective_message; fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else None)
        if kind!="captcha" or not fid: return
        await context.bot.send_photo(chat_id=chat,photo=fid,caption=f"🧩 تصویر کپچا برای درخواست {rid}\nلطفاً کد کپچا را ارسال کنید.")
        B.db.set_setting(f"final_relay_{uid}",f"captcha_wait|{rid}|{chat}")
        await msg.reply_text("✅ تصویر کپچا برای همکار ارسال شد. منتظر کد هستیم."); raise ApplicationHandlerStop

    async def relay_text(update, context):
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        if st.get("mode") in {"partner_send_code","final_partner_code","final_partner_captcha","final_partner_checkup"}:
            text=(update.effective_message.text or "").strip(); rid=st.get("code_request_rid") or st.get("final_relay_rid")
            if rid and text:
                admin_id=st.get("final_relay_admin") or B.db.setting(f"partner_code_request_admin_{rid}","") or next(iter(B.ADM),"")
                label="🔐 کد خدمت" if st.get("mode") in {"partner_send_code","final_partner_code"} else ("🧩 کد کپچا" if st.get("mode")=="final_partner_captcha" else "📝 متن چکاپ")
                ok=await send_to_admin(context,admin_id,f"📨 پاسخ همکار\n🎫 {B.db.conn.execute('SELECT tracking_code FROM requests WHERE id=?',(rid,)).fetchone()['tracking_code']}\n{label}: {text}",rid)
                st["mode"]=None; st.pop("code_request_rid",None); st.pop("final_relay_rid",None)
                return await update.effective_message.reply_text("✅ پاسخ برای مدیریت ارسال شد." if ok else "⚠️ پاسخ دریافت شد ولی ارسال به مدیریت ناموفق بود.",reply_markup=B.partner_kb())
        spec=B.db.setting(f"final_relay_{uid}","")
        if spec and spec.startswith("checkup|"):
            _,rid,chat=spec.split("|",2); text=(update.effective_message.text or "").strip()
            if text:
                await context.bot.send_message(chat_id=int(chat),text=f"📝 متن چکاپ درخواست {rid}:\n\n{text}")
                B.db.set_setting(f"final_relay_{uid}",""); return await update.effective_message.reply_text("✅ متن چکاپ برای همکار ارسال شد.")
        if st.get("mode")=="final_admin_chat":
            chat=int(st.get("final_chat_partner")); text=(update.effective_message.text or "").strip()
            if text: await context.bot.send_message(chat_id=chat,text=f"👔 مدیریت:\n{text}"); return
        if st.get("mode")=="final_partner_chat":
            admin=int(st.get("final_chat_admin")); text=(update.effective_message.text or "").strip()
            if text: await context.bot.send_message(chat_id=admin,text=f"👥 همکار:\n{text}"); return

    async def quick_buttons(update, context):
        msg=update.effective_message
        if not msg or not msg.text: return
        uid=update.effective_user.id; t=msg.text.strip(); st=B.S.setdefault(uid,{})
        if t=="💬 ارتباط با مدیریت" and st.get("partner_id"):
            admin_id=next(iter(B.ADM),None)
            if not admin_id: return
            st["mode"]="final_partner_chat"; st["final_chat_admin"]=int(admin_id)
            await context.bot.send_message(chat_id=int(admin_id),text=f"💬 همکار {st.get('partner_id')} درخواست ارتباط با مدیریت دارد.")
            return await msg.reply_text("💬 ارتباط با مدیریت فعال شد. پیام، عکس یا صوت خود را ارسال کنید.",reply_markup=B.partner_kb())
        if t=="💬 ارتباط با همکار" and B.admin(uid):
            return await msg.reply_text("💬 برای شروع چت، از داخل یک درخواست روی «💬 ارتباط با همکار» بزنید.",reply_markup=B.amenu())

    async def relay_media(update, context):
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        if st.get("mode")=="final_admin_chat":
            chat=int(st.get("final_chat_partner")); msg=update.effective_message
            if msg.photo: await context.bot.send_photo(chat,msg.photo[-1].file_id,caption="👔 تصویر از مدیریت")
            elif msg.voice: await context.bot.send_voice(chat,msg.voice.file_id,caption="👔 صوت از مدیریت")
            elif msg.document: await context.bot.send_document(chat,msg.document.file_id,caption="👔 فایل از مدیریت")
            raise ApplicationHandlerStop
        if st.get("mode")=="final_partner_chat":
            admin=int(st.get("final_chat_admin")); msg=update.effective_message
            if msg.photo: await context.bot.send_photo(admin,msg.photo[-1].file_id,caption="👥 تصویر از همکار")
            elif msg.voice: await context.bot.send_voice(admin,msg.voice.file_id,caption="👥 صوت از همکار")
            elif msg.document: await context.bot.send_document(admin,msg.document.file_id,caption="👥 فایل از همکار")
            raise ApplicationHandlerStop

    old_pkb=B.partner_kb
    def partner_kb(*args,**kwargs):
        base=old_pkb(*args,**kwargs); rows=[list(r) for r in base.keyboard]
        if not any("ارتباط با مدیریت" in str(x) for r in rows for x in r): rows.insert(-1,["💬 ارتباط با مدیریت"])
        return type(base)(rows,resize_keyboard=True)
    B.partner_kb=partner_kb

    old_amenu=B.amenu
    def amenu(*args,**kwargs):
        base=old_amenu(*args,**kwargs); rows=[list(r) for r in base.keyboard]
        if not any("ارتباط با همکار" in str(x) for r in rows for x in r): rows.insert(-1,["💬 ارتباط با همکار"])
        return type(base)(rows,resize_keyboard=True)
    B.amenu=amenu

    app.add_handler(CallbackQueryHandler(admin_cb,pattern=r"^(req:|panel:askcode:)"),group=-40000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,quick_buttons),group=-39999)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,relay_admin_media),group=-39998)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,relay_text),group=-39997)
    app.add_handler(MessageHandler(filters.PHOTO|filters.VOICE|filters.Document.ALL,relay_media),group=-39996)
    B._final_ops_overlay_v1=True
    return True
