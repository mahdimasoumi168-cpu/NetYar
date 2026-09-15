"""Final deterministic Government-service flow.
Owns the complete Telegram flow before legacy handlers.
"""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop

CANCEL="govv6:cancel"

def digits(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def cancel_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)]])
def docs_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("🪪 کارت آمایش",callback_data="govv6:card"),InlineKeyboardButton("🪪 کارت موقت",callback_data="govv6:temporary")],[InlineKeyboardButton("🛂 گذرنامه",callback_data="govv6:passport"),InlineKeyboardButton("📗 دفترچه اقامت",callback_data="govv6:residence")],[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)]])
def sim_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("📱 ارسال سند سیم‌کارت",callback_data="govv6:sim_yes")],[InlineKeyboardButton("⏭ بدون سند سیم‌کارت",callback_data="govv6:sim_no")],[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)]])
def type_name(t): return {"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"گذرنامه","residence_booklet":"دفترچه اقامت"}.get(t,"-")
def fid(msg):
    if getattr(msg,"photo",None): return msg.photo[-1].file_id
    if getattr(msg,"document",None): return msg.document.file_id
    return ""

def install(app,B):
    if getattr(B,"_gov_v6",False): return
    async def start(update,context):
        uid=update.effective_user.id; old=B.S.get(uid,{})
        if not old.get("partner_id"):
            await update.effective_message.reply_text("❌ این خدمت فقط از طریق پنل همکاران انجام می‌شود.\nابتدا وارد پنل همکاران شوید.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 پنل همکاران",callback_data="partner:panel")]])); return
        B.S[uid]={"mode":"govv6_doc_type","lang":old.get("lang","fa"),"partner_id":old.get("partner_id"),"partner_active":True}
        await update.effective_message.reply_text("🏛 حل مشکل سامانه دولت من\n\n🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=docs_kb())
    B.gov=start
    async def cancel(update,context):
        uid=update.effective_user.id; st=B.S.setdefault(uid,{}); pid=st.get("partner_id"); st.clear(); st.update({"status":"foreign","lang":"fa"})
        if pid: st.update({"partner_id":pid,"partner_active":True}); await update.effective_message.reply_text("❌ عملیات لغو شد.\n\n👥 به پنل همکاران بازگشتید.",reply_markup=B.partner_kb("fa")); return
        await update.effective_message.reply_text("❌ عملیات لغو شد.",reply_markup=B.main(uid))
    async def cb(update,context):
        q=update.callback_query
        if not q or not str(q.data or "").startswith("govv6:"): return
        await q.answer(); st=B.S.setdefault(q.from_user.id,{})
        a=str(q.data).split(":",1)[1]
        if a=="cancel": await cancel(q,context); raise ApplicationHandlerStop
        if a in {"card","temporary","passport","residence"}:
            st["gov_doc_type"]={"card":"card","temporary":"temporary_card","passport":"passport","residence":"residence_booklet"}[a]; st["mode"]="govv6_phone"
            await q.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if a=="sim_yes": st["mode"]="govv6_sim"; await q.message.reply_text("📱 لطفاً سند سیم‌کارت مشترک را ارسال کنید:",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if a=="sim_no": await create(update,context,st); raise ApplicationHandlerStop
    async def text(update,context):
        m=update.message
        if not m:return
        st=B.S.setdefault(update.effective_user.id,{}); mode=st.get("mode")
        if mode not in {"govv6_phone","govv6_dob","govv6_unique","govv6_special","govv6_family","govv6_identity","govv6_postal"}: return
        d=digits(m.text.strip())
        if mode=="govv6_phone":
            p=re.sub(r"\D","",d); p=("0"+p[2:]) if p.startswith("98") and len(p)==12 else p
            ok=bool(re.fullmatch(r"09\d{9}",p)); msg="❌ شماره موبایل باید دقیقاً ۱۱ رقم و با ۰۹ شروع شود." if not ok else "🎂 تاریخ تولد مشترک را وارد کنید:"
            if ok: st.update(gov_phone=p,mode="govv6_dob")
            await m.reply_text(msg,reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if mode=="govv6_dob":
            ok=bool(re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])",d));
            if ok: st.update(gov_dob=d,mode="govv6_unique")
            await m.reply_text("❌ تاریخ تولد نامعتبر است." if not ok else "🆔 شناسه یکتای مشترک را وارد کنید:",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if mode=="govv6_unique":
            ok=bool(re.fullmatch(r"9\d{9}",d));
            if ok: st.update(gov_unique=d,mode="govv6_special")
            await m.reply_text("❌ شناسه یکتا باید دقیقاً ۱۰ رقم و با ۹ شروع شود." if not ok else "🔖 شناسه اختصاصی مشترک را وارد کنید:",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if mode=="govv6_special":
            ok=bool(re.fullmatch(r"1\d{11}",d));
            if ok:
                st["gov_special"]=d
                if st.get("gov_doc_type") in {"card","temporary_card"}: st["mode"]="govv6_family"; prompt="👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید (حداقل ۵ رقم):"
                else: st["mode"]="govv6_identity"; prompt="🛂 شماره گذرنامه مشترک را وارد کنید:" if st.get("gov_doc_type")=="passport" else "📗 شماره دفترچه اقامت مشترک را وارد کنید:"
            else: prompt="❌ شناسه اختصاصی باید دقیقاً ۱۲ رقم و با ۱ شروع شود."
            await m.reply_text(prompt,reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if mode=="govv6_family":
            ok=bool(re.fullmatch(r"\d{5,}",d));
            if ok: st.update(gov_family=d,mode="govv6_postal")
            await m.reply_text("❌ کد خانوار باید حداقل ۵ رقم باشد." if not ok else "📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if mode=="govv6_identity":
            ok=bool(re.fullmatch(r"\d{3,}",d));
            if ok: st.update(gov_identity=d,mode="govv6_postal")
            await m.reply_text("❌ شماره مدرک را صحیح وارد کنید." if not ok else "📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        if mode=="govv6_postal":
            ok=bool(re.fullmatch(r"\d{10}",d));
            if ok:
                st["gov_postal"]=d; typ=st.get("gov_doc_type")
                if typ=="passport": st["mode"]="govv6_p1"; prompt="📸 ۱/۳ — عکس صفحه اول پاسپورت مشترک را ارسال کنید:"
                elif typ=="residence_booklet": st["mode"]="govv6_r1"; prompt="📗 ۱/۲ — عکس اول دفترچه اقامت مشترک را ارسال کنید:"
                else: st["mode"]="govv6_card"; prompt="🪪 ۱/۱ — عکس مدرک مشترک را ارسال کنید:"
            else: prompt="❌ کد پستی باید دقیقاً ۱۰ رقم باشد."
            await m.reply_text(prompt,reply_markup=cancel_kb()); raise ApplicationHandlerStop
    async def media(update,context):
        m=update.message
        if not m:return
        st=B.S.setdefault(update.effective_user.id,{}); mode=st.get("mode"); f=fid(m)
        if mode not in {"govv6_card","govv6_p1","govv6_p2","govv6_p3","govv6_r1","govv6_r2","govv6_sim"}: return
        if not f: await m.reply_text("❌ لطفاً عکس یا فایل مدرک را ارسال کنید.",reply_markup=cancel_kb()); raise ApplicationHandlerStop
        nxt={"govv6_card":("gov_card", "📱 سند سیم‌کارت مشترک اختیاری است."),"govv6_p1":("gov_p1","📸 ۲/۳ — عکس صفحه تمدید پاسپورت را ارسال کنید:"),"govv6_p2":("gov_p2","📸 ۳/۳ — عکس صفحه تمدید/روادید پاسپورت را ارسال کنید:"),"govv6_r1":("gov_r1","📗 ۲/۲ — عکس دوم دفترچه اقامت مشترک را ارسال کنید:"),"govv6_r2":("gov_r2","📱 سند سیم‌کارت مشترک اختیاری است:")}
        if mode=="govv6_sim": st["gov_sim"]=f; await create(update,context,st); raise ApplicationHandlerStop
        key,prompt=nxt[mode]; st[key]=f
        if mode=="govv6_p1": st["mode"]="govv6_p2"
        elif mode=="govv6_p2": st["mode"]="govv6_p3"; prompt="📱 سند سیم‌کارت مشترک اختیاری است:"
        elif mode=="govv6_p3": st["mode"]="govv6_sim_optional"; prompt="📱 سند سیم‌کارت مشترک اختیاری است:"; st["mode"]="govv6_sim_optional"
        elif mode=="govv6_r1": st["mode"]="govv6_r2"
        elif mode=="govv6_r2": st["mode"]="govv6_sim_optional"; prompt="📱 سند سیم‌کارت مشترک اختیاری است:"
        elif mode=="govv6_card": st["mode"]="govv6_sim_optional"
        if st.get("mode")=="govv6_sim_optional": await m.reply_text(prompt+"\nاگر دارید ارسال کنید؛ در غیر این صورت «بدون سند سیم‌کارت» را بزنید:",reply_markup=sim_kb())
        else: await m.reply_text(prompt,reply_markup=cancel_kb())
        raise ApplicationHandlerStop
    async def create(update,context,st):
        uid=update.effective_user.id; pid=st.get("partner_id")
        amount=int(B.db.setting("price_government","500000") or 500000)
        if not pid:
            await update.effective_message.reply_text("❌ درخواست معتبر نیست؛ پنل همکاران فعال نیست."); return
        row=B.db.conn.execute("SELECT balance,active FROM partners WHERE id=?",(pid,)).fetchone(); bal=int(row["balance"] or 0) if row else 0
        if not row or not row["active"] or bal<amount:
            await update.effective_message.reply_text(f"❌ اعتبار حساب همکار کافی نیست.\n💳 اعتبار: {bal:,} تومان\n💰 هزینه خدمت: {amount:,} تومان\n\nابتدا حساب را شارژ کنید.",reply_markup=B.partner_kb("fa")); return
        cur=B.db.conn.execute("UPDATE partners SET balance=balance-? WHERE id=? AND active=1 AND balance>=?",(amount,pid,amount)); B.db.conn.commit()
        if cur.rowcount!=1:
            await update.effective_message.reply_text("❌ اعتبار در لحظه ثبت درخواست کافی نبود. لطفاً دوباره تلاش کنید.",reply_markup=B.partner_kb("fa")); return
        try:
            owner=pid; rid,code=B.db.create_request(owner,"government","telegram",amount)
            typ=st.get("gov_doc_type"); fields=[("doc_type",typ),("phone",st.get("gov_phone")),("dob",st.get("gov_dob")),("unique_id",st.get("gov_unique")),("special_id",st.get("gov_special")),("postal_code",st.get("gov_postal")),("partner_id",str(pid)),("requester_telegram_id",str(uid))]
            if typ in {"card","temporary_card"}: fields.append(("family_code",st.get("gov_family")))
            if typ=="passport": fields.append(("passport",st.get("gov_identity")))
            if typ=="residence_booklet": fields.append(("booklet_number",st.get("gov_identity")))
            for k,v in fields:
                if v:B.db.answer(rid,k,answer=v)
            if typ=="passport": files=[("passport_first_page",st.get("gov_p1")),("passport_renewal_page",st.get("gov_p2")),("passport_visa_renewal_page",st.get("gov_p3"))]
            elif typ=="residence_booklet": files=[("residence_first_page",st.get("gov_r1")),("residence_renewal_page",st.get("gov_r2"))]
            else: files=[("document",st.get("gov_card"))]
            if st.get("gov_sim"): files.append(("sim_card_document",st["gov_sim"]))
            for k,f in files:
                if f:B.db.answer(rid,k,file_id=f)
            B.db.conn.execute("UPDATE requests SET status='reviewing',payment_status='paid',payment_method='partner_balance',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
            summary=f"👔 مدیر — درخواست جدید\n🆕 حل مشکل سامانه دولت من\n🎫 کد پیگیری: {code}\n🪪 نوع مدرک: {type_name(typ)}\n📱 شماره موبایل مشترک: {st.get('gov_phone','-')}\n🎂 تاریخ تولد مشترک: {st.get('gov_dob','-')}\n🆔 شناسه یکتای مشترک: {st.get('gov_unique','-')}\n🔖 شناسه اختصاصی مشترک: {st.get('gov_special','-')}\n"
            if typ in {"card","temporary_card"}: summary+=f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_family','-')}\n"
            else: summary+=(f"🛂 شماره گذرنامه: {st.get('gov_identity','-')}\n" if typ=="passport" else f"📗 شماره دفترچه اقامت: {st.get('gov_identity','-')}\n")
            summary+=f"📮 کد پستی مشترک: {st.get('gov_postal','-')}\n💰 مبلغ: {amount:,} تومان\n💳 پرداخت: کسر خودکار از شارژ همکار\n📱 سند سیم‌کارت: {'ارسال شده' if st.get('gov_sim') else 'ارسال نشده'}"
            kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"rq:detail:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}")],[InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")]])
            for aid in B.ADM:
                try: await context.bot.send_message(int(aid),summary,reply_markup=kb)
                except Exception: pass
                for k,f in files:
                    if f:
                        try: await context.bot.send_photo(int(aid),f,caption=f"🎫 {code}\n{k}")
                        except Exception:
                            try: await context.bot.send_document(int(aid),f,caption=f"🎫 {code}\n{k}")
                            except Exception: pass
            st["mode"]=None; st["request_id"]=rid; st["tracking_code"]=code
            await update.effective_message.reply_text(f"✅ درخواست با موفقیت ثبت شد.\n🎫 کد پیگیری: {code}\n💳 هزینه از شارژ همکار کسر شد.",reply_markup=B.partner_kb("fa"))
        except Exception:
            B.db.conn.execute("UPDATE partners SET balance=balance+? WHERE id=?",(amount,pid));B.db.conn.commit(); raise
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^govv6:"),group=-1000000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-1000000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,media),group=-1000000)
    B._gov_v6=True
