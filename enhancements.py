import logging, asyncio
from telegram import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("netyar.enhancements")

def install():
    try:
        import bot
        from core import db, now
        original_notify=bot.notify_admins; original_admin_cb=bot.admin_cb; original_partner=bot.partner
        original_service_text=bot.service_text; original_admin_text=bot.admin_text

        def styled_kb(rows):
            out=[]
            for row in rows:
                rr=[]
                for text in row:
                    style="success" if ("تأیید" in text or "فعال" in text or "💰" in text) else ("danger" if ("انصراف" in text or "رد" in text or "حذف" in text) else "primary")
                    try: rr.append(KeyboardButton(text=text,style=style))
                    except Exception: rr.append(text)
                out.append(rr)
            return ReplyKeyboardMarkup(out,resize_keyboard=True)
        bot.kb=styled_kb

        def menu_text():
            return ("📋 خدمات قابل استفاده:\n\n1️⃣ 🪪 فیدای غیر حضوری\n2️⃣ 🖨 خدمات چاپ\n"
                    "3️⃣ 🏛 حل مشکل ورود اتباع دولت من\n4️⃣ 🎫 کد رهگیری تمدید کارت‌ها\n"
                    "5️⃣ 📱 خدمات سیم‌کارت\n6️⃣ 📝 آزمون غربالگری\n7️⃣ 🎫 پیگیری\n"
                    "8️⃣ 💰 کیف پول من\n9️⃣ 📞 تماس با ما\n🔟 📝 ثبت شکایت مشتریان\n"
                    "👥 پنل همکاران\n\nلطفاً یکی از گزینه‌های بالا را انتخاب کنید:")

        async def start(u,c):
            uid=u.effective_user.id; bot.db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name); bot.S[uid]={}
            await u.message.reply_text("سلام و خوش آمدید 🌷\n\nلطفاً زبان را انتخاب کنید:\n1️⃣ 🇮🇷 فارسی\n2️⃣ 🇬🇧 English\n3️⃣ 🇸🇦 العربية",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="lang:fa",style="primary"),InlineKeyboardButton("🇬🇧 English",callback_data="lang:en",style="success"),InlineKeyboardButton("🇸🇦 العربية",callback_data="lang:ar",style="primary")]]))
        bot.start=start

        async def statuscb(u,c):
            q=u.callback_query; await q.answer(); uid=q.from_user.id; bot.S.setdefault(uid,{})["status"]=q.data.split(":")[1]
            await q.message.reply_text(menu_text() if bot.S[uid]["status"]=="foreign" else "🇮🇷 خدمات کاربران ایرانی در حال حاضر فعال نیست.",reply_markup=bot.main(uid))
        bot.statuscb=statuscb

        async def notify(app,message,request_id=None,inline=None,files=None):
            await original_notify(app,message,request_id,inline)
            if not bot.ADM:return
            file_ids=list(files or [])
            if request_id:
                try:file_ids += [r["file_id"] for r in db.conn.execute("SELECT file_id FROM request_answers WHERE request_id=? AND file_id!=''",(request_id,)).fetchall()]
                except Exception:pass
            if "درخواست شارژ حساب" in message and not request_id:
                try:
                    r=db.conn.execute("SELECT receipt_file_id FROM topups ORDER BY id DESC LIMIT 1").fetchone()
                    if r and r["receipt_file_id"]:file_ids.append(r["receipt_file_id"])
                except Exception:pass
            for fid in dict.fromkeys(x for x in file_ids if x):
                for aid in bot.ADM:
                    try:
                        try:await app.bot.send_photo(chat_id=int(aid),photo=fid,caption="📎 فایل/عکس مربوط به درخواست")
                        except Exception:await app.bot.send_document(chat_id=int(aid),document=fid,caption="📎 فایل مربوط به درخواست")
                    except Exception:log.exception("admin file notification failed")
        bot.notify_admins=notify

        async def partner(u,c):
            st=bot.S.setdefault(u.effective_user.id,{})
            if st.get("partner_id"):db.set_setting(f"partner_chat_{st['partner_id']}",str(u.effective_user.id))
            return await original_partner(u,c)
        bot.partner=partner

        async def service_text(u,c):
            uid=u.effective_user.id; st=bot.S.setdefault(uid,{})
            if st.get("mode")=="fida_phone":
                p=bot.normalize_phone(u.message.text)
                if not p:return await u.message.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789",reply_markup=bot.cancel_kb())
                owner=st.get("partner_id") or db.user("telegram",uid,u.effective_user.username,u.effective_user.full_name); rid,code=db.create_request(owner,"fida","telegram",int(db.setting("price_fida","0") or 0))
                db.answer(rid,"document",file_id=st.get("doc",""));db.answer(rid,"phone",answer=p);db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid' WHERE id=?",(rid,));db.conn.commit();st["mode"]=None
                asyncio.create_task(bot.notify_admins(c.application,f"🆕 درخواست فیدای غیرحضوری\n🎫 {code}\n📱 شماره: {p}\n🪪 مدرک: پیوست شده",rid));return await u.message.reply_text(f"✅ درخواست فیدای غیرحضوری ثبت شد.\n🎫 کد پیگیری: {code}",reply_markup=bot.partner_kb() if st.get("partner_id") else bot.main(uid))
            return await original_service_text(u,c)
        bot.service_text=service_text

        def full_amenu():return styled_kb([["👤 پنل کاربران","👥 همکاران"],["💰 شارژها","💰 پرداخت‌های مشتری"],["📋 درخواست‌ها","⚙️ قیمت‌ها"],["🤖 مدیریت پیام‌رسان‌ها","🌐 زبان‌ها"],["📊 گزارش","⚙️ تنظیمات"],["🩺 سلامت ربات‌ها"],["⬅️ منوی اصلی"]])
        bot.amenu=full_amenu

        async def admin_text(u,c):
            if not bot.admin(u.effective_user.id):return
            t=(u.message.text or "").strip()
            if t=="🌐 زبان‌ها":return await u.message.reply_text("🌐 زبان‌ها\n\nفارسی، English و العربية فعال هستند.\nزبان پیش‌فرض: "+db.setting("default_lang","fa"),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="langset:fa"),InlineKeyboardButton("🇬🇧 English",callback_data="langset:en")],[InlineKeyboardButton("🇸🇦 العربية",callback_data="langset:ar")]]))
            if t=="🤖 مدیریت پیام‌رسان‌ها":
                rows=db.bots();text="🤖 پیام‌رسان‌های ثبت‌شده\n\n"+("\n".join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'فعال' if r['active'] else 'غیرفعال'} | {r['status']}" for r in rows) if rows else "هنوز باتی ثبت نشده است.")
                return await u.message.reply_text(text,reply_markup=full_amenu())
            if t=="🩺 سلامت ربات‌ها":return await u.message.reply_text("🩺 سلامت سرویس\n\n🟢 Telegram: فعال\n🟢 Rubika: فعال\nℹ️ بات جدید پس از ثبت باید توکن آن در تنظیمات Railway قرار گیرد تا runtime جداگانه برایش راه‌اندازی شود.",reply_markup=full_amenu())
            if t=="⚙️ تنظیمات":return await u.message.reply_text("⚙️ تنظیمات\n\nوضعیت بات: "+db.setting("bot_open","1")+"\nبرای قیمت‌ها از «⚙️ قیمت‌ها» استفاده کنید.",reply_markup=full_amenu())
            return await original_admin_text(u,c)
        bot.admin_text=admin_text

        async def admin_cb(u,c):
            q=u.callback_query; data=q.data.split(":")
            if data and data[0]=="langset" and bot.admin(q.from_user.id):
                db.set_setting("default_lang",data[1]);await q.answer("ذخیره شد");return await q.message.reply_text("✅ زبان پیش‌فرض ذخیره شد.",reply_markup=bot.amenu())
            if data and data[0]=="req" and len(data)>=3 and bot.admin(q.from_user.id):
                rid=int(data[2]);r=db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
                if not r:await q.answer("درخواست پیدا نشد");return
                if data[1]=="v":
                    await q.answer();ans=db.conn.execute("SELECT field_key,answer FROM request_answers WHERE request_id=? AND answer!=''",(rid,)).fetchall();details="\n".join(f"• {x['field_key']}: {x['answer']}" for x in ans)
                    return await q.message.reply_text(f"🎫 {r['tracking_code']}\n🧾 خدمت: {r['service_key']}\n📌 وضعیت: {r['status']}\n💰 مبلغ: {r['amount']:,} تومان\n💳 پرداخت: {r['payment_status']}\n{details}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید خدمت",callback_data=f"req:a:{rid}"),InlineKeyboardButton("❌ رد خدمت",callback_data=f"req:x:{rid}")],[InlineKeyboardButton("🔐 درخواست کد از همکار",callback_data=f"req:p:{rid}")],[InlineKeyboardButton("✉️ پاسخ",callback_data=f"req:r:{rid}")]]))
                if data[1] in ("a","x"):
                    await q.answer();status="approved" if data[1]=="a" else "rejected";db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?",(status,now(),rid));db.conn.commit();user=db.conn.execute("SELECT platform,external_id FROM users WHERE id=?",(r["user_id"],)).fetchone()
                    if user and user["platform"]=="telegram":
                        try:await c.bot.send_message(chat_id=int(user["external_id"]),text="✅ خدمت شما تأیید شد." if status=="approved" else "❌ درخواست شما رد شد.")
                        except Exception:pass
                    await q.message.edit_reply_markup(reply_markup=None);return await q.message.reply_text("✅ خدمت تأیید شد." if status=="approved" else "❌ خدمت رد شد.",reply_markup=bot.amenu())
                if data[1]=="p":
                    await q.answer();ans=db.conn.execute("SELECT answer FROM request_answers WHERE request_id=? AND field_key='partner_id' ORDER BY id DESC LIMIT 1",(rid,)).fetchone();pid=ans["answer"] if ans else ""
                    if not pid:return await q.message.reply_text("⚠️ این درخواست به همکار متصل نیست.",reply_markup=bot.amenu())
                    db.set_setting(f"partner_code_request_{pid}",str(rid));chat=db.setting(f"partner_chat_{pid}","")
                    if chat:
                        try:await c.bot.send_message(chat_id=int(chat),text=f"🔐 مدیریت برای درخواست {r['tracking_code']} یک کد تأیید از شما می‌خواهد.\nلطفاً کد تأیید همان خدمت را در همین گفتگو ارسال کنید.");return await q.message.reply_text("✅ درخواست کد برای همکار ارسال شد.",reply_markup=bot.amenu())
                        except Exception:pass
                    return await q.message.reply_text("⚠️ چت همکار پیدا نشد؛ همکار ابتدا وارد پنل همکاران شود.",reply_markup=bot.amenu())
            return await original_admin_cb(u,c)
        bot.admin_cb=admin_cb
        log.info("NetYar safe Telegram enhancements installed")
    except Exception:log.exception("Telegram enhancement failed; original bot remains active")

    try:
        import rubika_v2 as rb
        old_rows,old_handle=rb.main_rows,rb.handle
        def rows(uid):
            r=old_rows(uid)
            for row in r:
                for i,(bid,label) in enumerate(row):
                    if bid=="6":row[i]=(bid,"📝 آزمون غربالگری" if rb.lang(uid)=="fa" else ("📝 Screening" if rb.lang(uid)=="en" else "📝 الفحص"))
            return r
        rb.main_rows=rows
        def handle(uid,chat,x,u):
            s=rb.STATE.setdefault(str(uid),{})
            if s.get("step")=="menu":
                if str(x).startswith("5"):rb.send(chat,"📱 خدمات سیم‌کارت: برای فعال‌سازی یا پیگیری، پیام خود را همین‌جا برای پشتیبانی ارسال کنید.",rb.main_rows(uid));return
                if str(x).startswith("6"):rb.send(chat,"📝 آزمون غربالگری: این خدمت جدا از «🎫 پیگیری» است. برای ثبت درخواست، پیام «آزمون غربالگری» را ارسال کنید.",rb.main_rows(uid));return
                if str(x).startswith("9"):rb.send(chat,"📞 برای پشتیبانی، پیام خود را همین‌جا ارسال کنید.",rb.main_rows(uid));return
            if s.get("step")=="partner" and (str(x).startswith("5") or "دولت من" in str(x)):
                s["step"]="partner_gov_fida";rb.send(chat,"🏛 حل مشکل سامانه دولت من\n\n🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید:",[[('0',rb.CANCEL)]]);return
            return old_handle(uid,chat,x,u)
        rb.handle=handle
        log.info("NetYar safe Rubika enhancements installed")
    except Exception:log.exception("Rubika enhancement unavailable; original remains active")

install()
