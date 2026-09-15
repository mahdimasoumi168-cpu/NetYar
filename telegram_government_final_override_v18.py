"""Final deterministic government document flow override."""
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters
from payment_invoice import invoice_text, invoice_markup

CANCEL="govf:cancel"

def digits(v): return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
def fid(msg): return msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else "")
def cancel_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)]])
def docs_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("🪪 کارت آمایش",callback_data="govf:card"),InlineKeyboardButton("🪪 کارت موقت",callback_data="govf:temporary")],[InlineKeyboardButton("🛂 پاسپورت",callback_data="govf:passport"),InlineKeyboardButton("📗 دفترچه اقامت",callback_data="govf:residence")],[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)])
def sim_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("📱 ارسال سند سیم‌کارت",callback_data="govf:sim_yes")],[InlineKeyboardButton("⏭ بدون سند سیم‌کارت",callback_data="govf:sim_no")],[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)])
def renew_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("📸 بله، صفحه تمدید را می‌فرستم",callback_data="govf:renew_yes")],[InlineKeyboardButton("⏭ رد کردن صفحه تمدید",callback_data="govf:renew_no")],[InlineKeyboardButton("❌ انصراف",callback_data=CANCEL)])

def install(app,B):
    if getattr(B,"_gov_final_override_v18",False): return
    async def start(update,context):
        uid=update.effective_user.id; old=B.S.get(uid,{})
        B.S[uid]={"mode":"govf_doc","lang":old.get("lang","fa"),"partner_id":old.get("partner_id"),"partner_active":old.get("partner_active",True),"gov":{}}
        await update.effective_message.reply_text("🏛 حل مشکل سامانه دولت من\n\n🪪 نوع مدرک مشترک را انتخاب کنید:",reply_markup=docs_kb())
    B.gov=start
    async def cb(update,context):
        q=update.callback_query; data=str(q.data or "")
        if not data.startswith("govf:"): return
        await q.answer(); st=B.S.setdefault(q.from_user.id,{}); a=data.split(":",1)[1]
        if a=="cancel":
            pid=st.get("partner_id"); lang=st.get("lang","fa"); st.clear(); st.update(status="foreign",lang=lang)
            if pid: st.update(partner_id=pid,partner_active=True); kb=B.partner_kb(lang)
            else: kb=B.main(q.from_user.id)
            await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=kb); raise ApplicationHandlerStop
        if a in {"card","temporary","passport","residence"}:
            typ={"card":"card","temporary":"temporary_card","passport":"passport","residence":"residence_booklet"}[a]; st["gov"]={"doc_type":typ};st["mode"]="govf_phone"
            await q.message.reply_text("📱 شماره موبایل مشترک را وارد کنید:",reply_markup=cancel_kb());raise ApplicationHandlerStop
        if a=="sim_yes": st["mode"]="govf_sim";await q.message.reply_text("📱 سند سیم‌کارت مشترک را ارسال کنید:",reply_markup=cancel_kb());raise ApplicationHandlerStop
        if a=="sim_no": await create(update,context,st);raise ApplicationHandlerStop
        if a=="renew_yes":
            typ=st.get("gov",{}).get("doc_type")
            st["mode"]="govf_pass_renew" if typ=="passport" else "govf_res_renew"
            await q.message.reply_text("📸 صفحه تمدید را ارسال کنید:",reply_markup=cancel_kb());raise ApplicationHandlerStop
        if a=="renew_no":
            typ=st.get("gov",{}).get("doc_type")
            if typ=="passport": st["mode"]="govf_pass_visa";await q.message.reply_text("📸 عکس صفحه تمدید/روادید ویزا را ارسال کنید:",reply_markup=cancel_kb())
            else: st["mode"]="govf_sim_choice";await q.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است:",reply_markup=sim_kb())
            raise ApplicationHandlerStop
    async def text(update,context):
        st=B.S.setdefault(update.effective_user.id,{});m=st.get("mode")
        if not str(m or "").startswith("govf_"): return
        t=digits(update.message.text).strip(); g=st.setdefault("gov",{})
        if m=="govf_phone":
            p=re.sub(r"\D","",t); p="0"+p[2:] if p.startswith("98") and len(p)==12 else p
            if not re.fullmatch(r"09\d{9}",p): await update.message.reply_text("❌ شماره موبایل معتبر نیست.",reply_markup=cancel_kb())
            else:g["phone"]=p;st["mode"]="govf_dob";await update.message.reply_text("🎂 تاریخ تولد مشترک را وارد کنید (مثال 1385/05/12):",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
        if m=="govf_dob":
            if not re.fullmatch(r"1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])",t): await update.message.reply_text("❌ تاریخ تولد نامعتبر است.",reply_markup=cancel_kb())
            else:g["dob"]=t;st["mode"]="govf_unique";await update.message.reply_text("🆔 شناسه یکتای مشترک را وارد کنید:",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
        if m=="govf_unique":
            if not re.fullmatch(r"9\d{9}",t): await update.message.reply_text("❌ شناسه یکتا باید ۱۰ رقم و با ۹ شروع شود.",reply_markup=cancel_kb())
            else:g["unique_id"]=t;st["mode"]="govf_special";await update.message.reply_text("🔖 شناسه اختصاصی مشترک را وارد کنید:",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
        if m=="govf_special":
            if not re.fullmatch(r"1\d{11}",t): await update.message.reply_text("❌ شناسه اختصاصی باید ۱۲ رقم و با ۱ شروع شود.",reply_markup=cancel_kb())
            else:
                g["special_id"]=t;typ=g["doc_type"]
                if typ in {"card","temporary_card"}:st["mode"]="govf_family";await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار مشترک را وارد کنید:",reply_markup=cancel_kb())
                else:st["mode"]="govf_identity";await update.message.reply_text("🪪 شماره مدرک مشترک را وارد کنید:",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
        if m=="govf_family":
            if not re.fullmatch(r"\d{5,}",t): await update.message.reply_text("❌ کد خانوار نامعتبر است.",reply_markup=cancel_kb())
            else:g["family_code"]=t;st["mode"]="govf_postal";await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
        if m=="govf_identity":
            if not re.fullmatch(r"\d{3,}",t): await update.message.reply_text("❌ شماره مدرک نامعتبر است.",reply_markup=cancel_kb())
            else:g["identity_number"]=t;st["mode"]="govf_postal";await update.message.reply_text("📮 کد پستی ۱۰ رقمی منزل مشترک را وارد کنید:",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
        if m=="govf_postal":
            if not re.fullmatch(r"\d{10}",t): await update.message.reply_text("❌ کد پستی باید ۱۰ رقم باشد.",reply_markup=cancel_kb())
            else:
                g["postal_code"]=t;typ=g["doc_type"]
                if typ=="passport":st["mode"]="govf_pass_first";await update.message.reply_text("📸 ۱/۳ — عکس صفحه مشخصات پاسپورت را ارسال کنید:",reply_markup=cancel_kb())
                elif typ=="residence_booklet":st["mode"]="govf_res_first";await update.message.reply_text("📗 ۱/۲ — عکس صفحه مشخصات دفترچه اقامت را ارسال کنید:",reply_markup=cancel_kb())
                else:st["mode"]="govf_card";await update.message.reply_text("🪪 عکس کارت را ارسال کنید:",reply_markup=cancel_kb())
            raise ApplicationHandlerStop
    async def media(update,context):
        st=B.S.setdefault(update.effective_user.id,{});m=st.get("mode")
        if not str(m or "").startswith("govf_"): return
        f=fid(update.message)
        if not f: await update.message.reply_text("❌ عکس یا فایل معتبر ارسال کنید.",reply_markup=cancel_kb());raise ApplicationHandlerStop
        g=st.setdefault("gov",{})
        if m=="govf_pass_first":g["pass_first"]=f;st["mode"]="govf_pass_renew_choice";await update.message.reply_text("📸 صفحه تمدید پاسپورت را ارسال می‌کنید؟",reply_markup=renew_kb())
        elif m=="govf_pass_renew":g["pass_renew"]=f;st["mode"]="govf_pass_visa";await update.message.reply_text("📸 ۳/۳ — عکس صفحه تمدید/روادید ویزا را ارسال کنید:",reply_markup=cancel_kb())
        elif m=="govf_pass_visa":g["pass_visa"]=f;st["mode"]="govf_sim_choice";await update.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است:",reply_markup=sim_kb())
        elif m=="govf_res_first":g["res_first"]=f;st["mode"]="govf_res_renew_choice";await update.message.reply_text("📗 صفحه تمدید دفترچه اقامت اختیاری است. ارسال می‌کنید؟",reply_markup=renew_kb())
        elif m=="govf_res_renew":g["res_renew"]=f;st["mode"]="govf_sim_choice";await update.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است:",reply_markup=sim_kb())
        elif m=="govf_card":g["card_photo"]=f;st["mode"]="govf_sim_choice";await update.message.reply_text("📱 سند سیم‌کارت مشترک اختیاری است:",reply_markup=sim_kb())
        elif m=="govf_sim":g["sim_document"]=f;await create(update,context,st)
        else:return
        raise ApplicationHandlerStop
    async def create(update,context,st):
        uid=update.effective_user.id;g=st.get("gov",{});typ=g.get("doc_type");amount=int(B.db.setting("price_government","500000") or 500000);pid=st.get("partner_id")
        owner=pid or B.db.user("telegram",uid,update.effective_user.username,update.effective_user.full_name);rid,code=B.db.create_request(owner,"government","telegram",amount)
        fields=[("doc_type",typ),("phone",g.get("phone")),("dob",g.get("dob")),("unique_id",g.get("unique_id")),("special_id",g.get("special_id")),("postal_code",g.get("postal_code"))]
        if typ in {"card","temporary_card"}:fields.append(("family_code",g.get("family_code")))
        else:fields.append(("passport_number",g.get("identity_number")) if typ=="passport" else ("booklet_number",g.get("identity_number")))
        if pid:fields.append(("partner_id",str(pid)))
        for k,v in fields:
            if v:B.db.answer(rid,k,answer=v)
        if typ=="passport":files=[("passport_first_page",g.get("pass_first")),("passport_renewal_page",g.get("pass_renew")),("passport_visa_renewal_page",g.get("pass_visa"))]
        elif typ=="residence_booklet":files=[("residence_first_page",g.get("res_first")),("residence_renewal_page",g.get("res_renew"))]
        else:files=[("document",g.get("card_photo"))]
        for k,f in files:
            if f:B.db.answer(rid,k,file_id=f)
        if g.get("sim_document"):B.db.answer(rid,"sim_card_document",file_id=g["sim_document"])
        B.db.conn.execute("UPDATE requests SET status='awaiting_payment',payment_status='unpaid',payment_method='invoice',updated_at=? WHERE id=?",(B.now(),rid));B.db.conn.commit()
        names={"card":"کارت آمایش","temporary_card":"کارت موقت","passport":"پاسپورت","residence_booklet":"دفترچه اقامت"};lines=["👔 مدیر — درخواست جدید","🆕 حل مشکل سامانه دولت من",f"🎫 کد پیگیری: {code}",f"🪪 نوع مدرک: {names.get(typ,typ)}",f"📱 موبایل: {g.get('phone','-')}",f"🎂 تولد: {g.get('dob','-')}",f"🆔 شناسه یکتا: {g.get('unique_id','-')}",f"🔖 شناسه اختصاصی: {g.get('special_id','-')}",f"📮 کد پستی: {g.get('postal_code','-')}",f"📱 سند سیم‌کارت: {'ارسال شده' if g.get('sim_document') else 'اختیاری — ارسال نشده'}",f"💰 مبلغ: {amount:,} تومان"]
        if g.get("family_code"):lines.append(f"👨‍👩‍👧‍👦 کد خانوار: {g['family_code']}")
        if g.get("identity_number"):lines.append(f"🪪 شماره مدرک: {g['identity_number']}")
        controls=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"panel:req:{rid}")],[InlineKeyboardButton("📨 درخواست کد از همکار",callback_data=f"rq:ask:{rid}"),InlineKeyboardButton("⏳ بررسی اولیه",callback_data=f"rq:review:{rid}")],[InlineKeyboardButton("💰 تأیید دریافت وجه",callback_data=f"rq:payconfirm:{rid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"rq:reject:{rid}")]])
        for aid in list(dict.fromkeys(B.ADM)):
            try:await context.bot.send_message(chat_id=int(aid),text="\n".join(lines),reply_markup=controls)
            except Exception:pass
            for k,f in files+[("sim_card_document",g.get("sim_document"))]:
                if not f:continue
                try:await context.bot.send_photo(chat_id=int(aid),photo=f,caption=f"🎫 {code}\n📎 {k}")
                except Exception:
                    try:await context.bot.send_document(chat_id=int(aid),document=f,caption=f"🎫 {code}\n📎 {k}")
                    except Exception:pass
        st["mode"]="invoice_pending";st["request_id"]=rid;st["tracking_code"]=code
        await update.effective_message.reply_text(invoice_text("فاکتور خدمات حل مشکل سامانه دولت من",amount,code,B),reply_markup=invoice_markup(B),parse_mode="HTML")
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^govf:"),group=-300000)
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media),group=-299999)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-299999)
    B._gov_final_override_v18=True
