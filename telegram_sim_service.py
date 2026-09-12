"""Telegram SIM-card purchase flow for NetYar.

Purchase is enabled; replacement is intentionally closed for all carriers.
The flow collects the requested identity documents, a reachable/self-owned
mobile number, the 12-digit FIDA code, and the card-to-card receipt, then
forwards the complete request to admins.
"""
import logging
import re
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.sim_service")
CARRIERS = {"ایرانسل", "رایتل", "سامانتل"}
DOCS = {"کارت آمایش", "کارت موقت", "پاسپورت", "دفترچه اقامت"}


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

def _phone(v):
    s = _digits(v).strip().replace(" ", "").replace("-", "")
    if s.startswith("+98"): s = "0" + s[3:]
    elif s.startswith("0098"): s = "0" + s[4:]
    return s if re.fullmatch(r"09\d{9}", s) else None

def _fida(v):
    s = _digits(v).strip().replace(" ", "").replace("-", "")
    return s if re.fullmatch(r"1\d{11}", s) else None

def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data="sim:" + k) for k,t in row] for row in rows])

def start(B, uid, message):
    st = B.S.setdefault(uid, {})
    st.update(mode="sim_carrier", sim={"files": []})
    return message.reply_text("📱 خدمات سیم کارت\n\nلطفاً نوع سیم کارت را انتخاب کنید:", reply_markup=_kb([[('irancell','ایرانسل'),('rightel','رایتل')],[('samantel','سامانتل')],[('cancel','❌ انصراف')]]))

async def callback(update, context, B):
    q=update.callback_query; data=str(q.data or '')
    if not data.startswith('sim:'): return
    await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
    act=data.split(':',1)[1]
    if act=='cancel':
        st['mode']=None; return await q.message.reply_text('❌ عملیات لغو شد.',reply_markup=B.partner_kb(st.get('lang','fa')) if st.get('partner_id') else B.main(uid))
    if act in {'irancell','rightel','samantel'}:
        carrier={'irancell':'ایرانسل','rightel':'رایتل','samantel':'سامانتل'}[act]
        st['sim']['carrier']=carrier; st['mode']='sim_type'
        return await q.message.reply_text(f'📱 اپراتور: {carrier}\n\nنوع خدمت را انتخاب کنید:',reply_markup=_kb([[('buy','خرید سیم کارت'),('replace','تعویض سیم کارت')],[('cancel','❌ انصراف')]]))
    if act=='replace':
        return await q.message.reply_text('⛔ تعویض سیم کارت فعلاً بسته می‌باشد.\n\nدر حال حاضر فقط خرید سیم کارت برای هر سه اپراتور فعال است.',reply_markup=_kb([[('buy','خرید سیم کارت')],[('cancel','❌ انصراف')]]))
    if act=='buy':
        st['sim']['service']='خرید سیم کارت'; st['mode']='sim_doc';
        return await q.message.reply_text('🪪 نوع مدرک را انتخاب کنید:',reply_markup=_kb([[('doc_amayesh','کارت آمایش'),('doc_temp','کارت موقت')],[('doc_passport','پاسپورت'),('doc_booklet','دفترچه اقامت')],[('cancel','❌ انصراف')]]))
    if act.startswith('doc_'):
        doc={'doc_amayesh':'کارت آمایش','doc_temp':'کارت موقت','doc_passport':'پاسپورت','doc_booklet':'دفترچه اقامت'}[act]
        st['sim']['doc_type']=doc; st['sim']['files']=[]
        if doc=='کارت آمایش': st['mode']='sim_doc_amayesh'; prompt='📸 عکس کارت آمایش را ارسال کنید.'
        elif doc=='کارت موقت': st['mode']='sim_doc_temp'; prompt='📸 عکس کارت موقت را ارسال کنید.'
        elif doc=='پاسپورت': st['mode']='sim_passport_first'; prompt='📸 ابتدا عکس صفحه اول مشخصات پاسپورت را ارسال کنید.'
        else: st['mode']='sim_booklet_first'; prompt='📸 ابتدا عکس صفحه اول مشخصات دفترچه اقامت را ارسال کنید.'
        return await q.message.reply_text(prompt,reply_markup=B.cancel_kb(st.get('lang','fa')))
    if act=='passport_skip_renew':
        st['mode']='sim_passport_residence'; return await q.message.reply_text('📸 حالا عکس صفحه اقامت پاسپورت را ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if act=='booklet_skip_renew':
        st['mode']='sim_booklet_done'; return await q.message.reply_text('📸 حالا عکس صفحه مشخصات دفترچه را در صورت نیاز تکمیل کنید، سپس ادامه را بزنید.',reply_markup=_kb([[('continue_after_booklet','ادامه')],[('cancel','❌ انصراف')]]))
    if act=='passport_renew': st['mode']='sim_passport_residence'; return await q.message.reply_text('📸 عکس صفحه تمدید پاسپورت را ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if act=='booklet_renew': st['mode']='sim_booklet_done'; return await q.message.reply_text('📸 عکس تمدید دفترچه اقامت را ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if act=='continue_after_booklet': st['mode']='sim_phone'; return await q.message.reply_text('📱 شماره موبایل به نام خودتان را وارد کنید.\nاگر ندارید، یک شماره سیم کارت در دسترس وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if act=='continue_after_docs': st['mode']='sim_phone'; return await q.message.reply_text('📱 شماره موبایل به نام خودتان را وارد کنید.\nاگر ندارید، یک شماره سیم کارت در دسترس وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if act=='accept_fee':
        st['mode']='sim_receipt'; return await q.message.reply_text('💳 هزینه را طبق مبلغ اعلام‌شده کارت‌به‌کارت کنید و سپس عکس رسید را ارسال کنید.\n\nبعد از دریافت رسید، مشخصات و مدارک کامل برای مدیریت ارسال می‌شود.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    raise ApplicationHandlerStop

async def text(update, context, B):
    msg=update.effective_message; uid=update.effective_user.id; st=B.S.setdefault(uid,{}); mode=st.get('mode'); t=(msg.text or '').strip()
    if mode=='sim_phone':
        p=_phone(t)
        if not p: return await msg.reply_text('❌ شماره موبایل معتبر نیست. مثال: 09123456789',reply_markup=B.cancel_kb(st.get('lang','fa')))
        st['sim']['phone']=p; st['mode']='sim_fida'; return await msg.reply_text('🔢 کد فیدا را وارد کنید.\nکد باید ۱۲ رقم باشد و با عدد ۱ شروع شود.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if mode=='sim_fida':
        f=_fida(t)
        if not f: return await msg.reply_text('❌ کد فیدا نامعتبر است. باید دقیقاً ۱۲ رقم باشد و با ۱ شروع شود.',reply_markup=B.cancel_kb(st.get('lang','fa')))
        st['sim']['fida']=f; st['mode']='sim_fee_accept'; return await msg.reply_text('💰 هزینه خرید سیم کارت برای شما اعلام/تأیید می‌شود. پس از تأیید هزینه، پرداخت کارت‌به‌کارت را انجام دهید.',reply_markup=_kb([[('accept_fee','✅ تأیید هزینه و ادامه')],[('cancel','❌ انصراف')]]))
    if mode=='sim_fee_accept':
        if t in {'✅ تأیید هزینه و ادامه','تأیید هزینه'}: st['mode']='sim_receipt'; return await msg.reply_text('💳 لطفاً هزینه اعلام‌شده را کارت‌به‌کارت کنید و عکس رسید را ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if mode=='sim_passport_renew_choice': return
    if mode=='sim_booklet_renew_choice': return

async def media(update, context, B):
    msg=update.effective_message; uid=update.effective_user.id; st=B.S.setdefault(uid,{}); mode=st.get('mode')
    if not mode.startswith('sim_'): return
    fid=msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else '')
    if not fid: return await msg.reply_text('❌ عکس یا فایل معتبر ارسال کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    sim=st.setdefault('sim',{}); sim.setdefault('files',[])
    if mode in {'sim_doc_amayesh','sim_doc_temp'}:
        sim['files'].append(('مدرک شناسایی',fid)); st['mode']='sim_phone'
        return await msg.reply_text('✅ مدرک دریافت شد.\n\n📱 شماره موبایل به نام خودتان را وارد کنید. اگر ندارید، یک شماره سیم کارت در دسترس وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if mode=='sim_passport_first':
        sim['files'].append(('صفحه اول پاسپورت',fid)); st['mode']='sim_passport_renew_choice'
        return await msg.reply_text('📸 صفحه تمدید پاسپورت اختیاری است. ارسال می‌کنید؟',reply_markup=_kb([[('passport_renew','بله، ارسال می‌کنم'),('passport_skip_renew','خیر، رد می‌کنم')],[('cancel','❌ انصراف')]]))
    if mode=='sim_passport_residence':
        sim['files'].append(('صفحه اقامت پاسپورت',fid)); st['mode']='sim_phone'
        return await msg.reply_text('✅ مدارک پاسپورت دریافت شد.\n\n📱 شماره موبایل به نام خودتان را وارد کنید. اگر ندارید، یک شماره سیم کارت در دسترس وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if mode=='sim_passport_renew_choice': return
    if mode=='sim_booklet_first':
        sim['files'].append(('صفحه اول دفترچه اقامت',fid)); st['mode']='sim_booklet_renew_choice'
        return await msg.reply_text('📸 صفحه تمدید دفترچه اقامت اختیاری است. ارسال می‌کنید؟',reply_markup=_kb([[('booklet_renew','بله، ارسال می‌کنم'),('booklet_skip_renew','خیر، رد می‌کنم')],[('cancel','❌ انصراف')]]))
    if mode=='sim_booklet_done':
        sim['files'].append(('دفترچه اقامت',fid)); st['mode']='sim_phone'
        return await msg.reply_text('✅ مدرک دفترچه دریافت شد.\n\n📱 شماره موبایل به نام خودتان را وارد کنید. اگر ندارید، یک شماره سیم کارت در دسترس وارد کنید.',reply_markup=B.cancel_kb(st.get('lang','fa')))
    if mode=='sim_receipt':
        sim['receipt']=fid; st['mode']='sim_done'
        carrier=sim.get('carrier','-'); doc=sim.get('doc_type','-'); phone=sim.get('phone','-'); fida=sim.get('fida','-')
        text=(f'🆕 درخواست خرید سیم کارت\n\n📱 اپراتور: {carrier}\n🛒 خدمت: خرید سیم کارت\n🪪 نوع مدرک: {doc}\n📞 موبایل در دسترس: {phone}\n🔢 کد فیدا: {fida}\n\n📎 مدارک: {len(sim.get("files",[]))} فایل\n💳 رسید کارت‌به‌کارت پیوست شده است.')
        for aid in B.ADM:
            try:
                await context.bot.send_message(chat_id=int(aid),text=text)
                for name,file_id in sim.get('files',[]):
                    await context.bot.send_photo(chat_id=int(aid),photo=file_id,caption=f'📎 {name}')
                await context.bot.send_photo(chat_id=int(aid),photo=fid,caption='💳 رسید کارت‌به‌کارت')
            except Exception: log.exception('SIM admin forwarding failed')
        st['mode']=None
        return await msg.reply_text('✅ درخواست خرید سیم کارت ثبت شد و مشخصات، مدارک و رسید برای مدیریت ارسال شد.',reply_markup=B.partner_kb(st.get('lang','fa')) if st.get('partner_id') else B.main(uid))


def install(app,B):
    if getattr(B,'_telegram_sim_service',False): return
    B.sim_start=lambda update,context: start(B,update.effective_user.id,update.effective_message)
    app.add_handler(CallbackQueryHandler(lambda u,c: callback(u,c,B),pattern=r'^sim:'),group=-3000)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL,lambda u,c: media(u,c,B)),group=-2999)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c: text(u,c,B)),group=-2999)
    B._telegram_sim_service=True
