import os
import time
import logging
import re
import requests
from core import db, now, check_password

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("netyar.rubika")

TOKEN = os.getenv("RUBIKA_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("RUBIKA_BOT_TOKEN environment variable is missing.")

BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"
HTTP = requests.Session()
HTTP.headers.update({"Content-Type": "application/json"})

CANCEL = "❌ انصراف"
OK = "✅ تأیید"

TEXT = {
    "fa": {
        "lang": "🌐 زبان را انتخاب کنید:", "cit": "آیا اتباع هستید یا ایرانی؟", "iran": "🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.",
        "menu": "سلام 👋\nخدمت موردنظر را انتخاب کنید:", "fida": "🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.", "fida_phone": "📱 شماره موبایل مشترک را وارد کنید.",
        "gov_fida": "🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید.", "gov_yekta": "🔢 شناسه یکتای مشترک را وارد کنید.", "id": "🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.",
        "phone": "📱 شماره موبایل مشترک را وارد کنید. سیم‌کارت باید به نام خود مشترک باشد.", "dob": "🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.",
        "doc": "📄 اگر سند سیم‌کارت دارید تصویر آن را ارسال کنید؛ در غیر این صورت «ندارم» را بزنید.", "print": "🖨 نوع چاپ را انتخاب کنید:", "side": "📄 نوع چاپ را انتخاب کنید:",
        "copies": "🔢 تعداد نسخه موردنیاز از هر صفحه را وارد کنید.", "files": "📎 فایل‌ها یا عکس‌ها را یکی‌یکی ارسال کنید. در پایان «تأیید» را بزنید.",
        "received": "✅ دریافت شد. مورد بعدی را بفرستید یا «تأیید» را بزنید.", "track": "🎫 کد پیگیری را وارد کنید.", "bad": "لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.",
        "cancel": "عملیات لغو شد. به منوی اصلی برگشتید. ✅", "confirm": "برای ادامه «تأیید» و برای لغو «انصراف» را انتخاب کنید.",
        "thanks": "درخواست شما ثبت شد ✅\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان", "no_track": "❌ کد پیگیری پیدا نشد.",
        "payment": "🧾 فاکتور\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان\n\n💳 شماره کارت: {card}\nبه نام: {owner}\n\nپس از واریز، رسید را ارسال کنید.",
        "balance": "💰 موجودی اعتبار شما: {amount:,} تومان", "login_phone": "📱 شماره همراه همکار را وارد کنید.", "login_pass": "🔐 رمز عبور همکار را وارد کنید.",
        "no_partner": "❌ همکار پیدا نشد.", "bad_login": "❌ شماره همراه یا رمز عبور نادرست است.", "topup_amount": "💰 مبلغ شارژ را به تومان وارد کنید.",
        "topup_receipt": "📸 رسید واریز را ارسال کنید.", "topup_sent": "رسید شارژ #{id} ثبت شد و منتظر تأیید مدیر است. ✅",
        "gov_done": "درخواست ثبت شد و برای بررسی/انجام خدمت به اپراتور ارسال شد. ✅\n🎫 کد پیگیری: {code}",
        "gov_retry": "سامانه دولتی در حال حاضر پاسخ قابل اتکا نداد. لطفاً بعداً دوباره امتحان کنید. برای این شناسه یکتا، پرداخت مجدد لازم نیست.",
    },
    "en": {
        "lang": "🌐 Choose your language:", "cit": "Are you a foreign national or Iranian?", "iran": "🇮🇷 Services are currently unavailable for Iranian users.",
        "menu": "Hello 👋\nChoose a service:", "fida": "🪪 Send the customer's identification document.", "fida_phone": "📱 Enter the customer's mobile number.",
        "gov_fida": "🆔 Enter the customer's FIDA/special ID.", "gov_yekta": "🔢 Enter the customer's unique ID.", "id": "🪪 Send the customer's identification document.",
        "phone": "📱 Enter the customer's mobile number. The SIM must be registered to the customer.", "dob": "🎂 Enter the customer's birth date as 1356/01/01.",
        "doc": "📄 Send the SIM ownership document, or choose No.", "print": "🖨 Choose print type:", "side": "📄 Choose printing mode:",
        "copies": "🔢 Enter copies per page.", "files": "📎 Send files/images one by one. Choose Confirm when finished.", "received": "✅ Received. Send another item or choose Confirm.",
        "track": "🎫 Enter the tracking code.", "bad": "Please choose one of the displayed options.", "cancel": "Operation cancelled. Back to the main menu. ✅",
        "confirm": "Choose Confirm to continue or Cancel to stop.", "thanks": "Request registered ✅\n🎫 Tracking code: {code}\n💰 Amount: {amount:,} toman", "no_track": "❌ Tracking code not found.",
        "payment": "🧾 Invoice\n🎫 Tracking code: {code}\n💰 Amount: {amount:,} toman\n\n💳 Card: {card}\nOwner: {owner}\n\nSend the payment receipt after transfer.",
        "balance": "💰 Your balance: {amount:,} toman", "login_phone": "📱 Enter your partner phone number.", "login_pass": "🔐 Enter your partner password.",
        "no_partner": "❌ Partner not found.", "bad_login": "❌ Invalid phone or password.", "topup_amount": "💰 Enter the top-up amount in toman.", "topup_receipt": "📸 Send the transfer receipt.",
        "topup_sent": "Top-up receipt #{id} submitted for manager approval. ✅", "gov_done": "Request submitted for operator review. ✅\n🎫 Tracking code: {code}",
        "gov_retry": "The government system did not respond reliably. Please try again later. No second payment is required for the same unique ID.",
    },
    "ar": {
        "lang": "🌐 اختر اللغة:", "cit": "هل أنت من الرعايا الأجانب أم إيراني؟", "iran": "🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين.",
        "menu": "مرحباً 👋\nاختر الخدمة:", "fida": "🪪 أرسل صورة وثيقة هوية العميل.", "fida_phone": "📱 أدخل رقم هاتف العميل.",
        "gov_fida": "🆔 أدخل رقم فيدا/الرقم الخاص بالعميل.", "gov_yekta": "🔢 أدخل المعرف الفريد للعميل.", "id": "🪪 أرسل صورة وثيقة هوية العميل.",
        "phone": "📱 أدخل رقم هاتف العميل. يجب أن تكون الشريحة مسجلة باسم العميل.", "dob": "🎂 أدخل تاريخ الميلاد بالشكل 1356/01/01.",
        "doc": "📄 أرسل وثيقة ملكية الشريحة أو اختر لا يوجد.", "print": "🖨 اختر نوع الطباعة:", "side": "📄 اختر طريقة الطباعة:", "copies": "🔢 أدخل عدد النسخ لكل صفحة.",
        "files": "📎 أرسل الملفات أو الصور. عند الانتهاء اختر تأكيد.", "received": "✅ تم الاستلام. أرسل المزيد أو اختر تأكيد.", "track": "🎫 أدخل رمز المتابعة.",
        "bad": "يرجى اختيار أحد الخيارات المعروضة.", "cancel": "تم إلغاء العملية والعودة إلى القائمة الرئيسية. ✅", "confirm": "اختر تأكيد للمتابعة أو إلغاء للتوقف.",
        "thanks": "تم تسجيل الطلب ✅\n🎫 رمز المتابعة: {code}\n💰 المبلغ: {amount:,} تومان", "no_track": "❌ لم يتم العثور على رمز المتابعة.",
        "payment": "🧾 الفاتورة\n🎫 رمز المتابعة: {code}\n💰 المبلغ: {amount:,} تومان\n\n💳 البطاقة: {card}\nالمالك: {owner}\n\nأرسل إيصال الدفع بعد التحويل.",
        "balance": "💰 رصيدك: {amount:,} تومان", "login_phone": "📱 أدخل رقم هاتف الشريك.", "login_pass": "🔐 أدخل كلمة مرور الشريك.", "no_partner": "❌ لم يتم العثور على الشريك.",
        "bad_login": "❌ رقم الهاتف أو كلمة المرور غير صحيحة.", "topup_amount": "💰 أدخل مبلغ الشحن بالتومان.", "topup_receipt": "📸 أرسل إيصال التحويل.",
        "topup_sent": "تم إرسال إيصال الشحن #{id} للمراجعة. ✅", "gov_done": "تم إرسال الطلب للمراجعة من قبل المشغل. ✅\n🎫 رمز المتابعة: {code}",
        "gov_retry": "لم يستجب النظام الحكومي بشكل موثوق. يرجى المحاولة لاحقاً. لا يلزم دفع ثانٍ لنفس المعرف الفريد.",
    },
}

STATES = {}
ADMIN_COMMAND = os.getenv("ADMIN_COMMAND", "/" + "Admin" + "2025").strip()
ADMIN_IDS = {x.strip() for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip()}
def is_admin(uid): return str(uid) in ADMIN_IDS or STATES.get(uid, {}).get("admin") is True

def admin_menu():
    return buttons([[('1','👥 همکاران'),('2','💰 شارژها')],[('3','💳 پرداخت‌های مشتری'),('4','📋 درخواست‌ها')],[('5','⚙️ قیمت‌ها'),('6','📊 گزارش')],[('7','🚪 خروج از پنل')]])

def admin_action(uid, chat, text):
    if not is_admin(uid): return False
    if text in {'👥 همکاران','1'}:
        rows=db.conn.execute('SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC LIMIT 50').fetchall()
        send(chat,'\n'.join(f"#{r['id']} | {r['name']} | {r['phone']} | {int(r['balance']):,} تومان" for r in rows) or 'همکاری ثبت نشده است.',admin_menu()); return True
    if text in {'💰 شارژها','2'}:
        rows=db.conn.execute("SELECT t.id,t.amount,t.status,p.name FROM topups t JOIN partners p ON p.id=t.partner_id ORDER BY t.id DESC LIMIT 30").fetchall()
        extra=[(f"تأیید شارژ #{r['id']}",f"رد شارژ #{r['id']}") for r in rows if r['status']=='pending']
        send(chat,'\n'.join(f"#{r['id']} | {r['name']} | {int(r['amount']):,} | {r['status']}" for r in rows) or 'شارژی وجود ندارد.',extra+admin_menu()); return True
    if text in {'💳 پرداخت‌های مشتری','3'}:
        rows=db.conn.execute("SELECT id,tracking_code,service_key,amount,payment_status FROM requests WHERE payment_status='pending' ORDER BY id DESC LIMIT 30").fetchall()
        extra=[(f"تأیید پرداخت #{r['id']}",f"رد پرداخت #{r['id']}") for r in rows]
        send(chat,'\n'.join(f"#{r['id']} | {r['tracking_code']} | {r['service_key']} | {int(r['amount']):,} تومان" for r in rows) or 'پرداخت معلقی نیست.',extra+admin_menu()); return True
    if text in {'📋 درخواست‌ها','4'}:
        rows=db.conn.execute('SELECT tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 50').fetchall()
        send(chat,'\n'.join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,} | {r['payment_status']}" for r in rows) or 'درخواستی نیست.',admin_menu()); return True
    if text in {'⚙️ قیمت‌ها','5'}:
        STATES[uid]['step']='admin_price'; send(chat,'⚙️ قیمت را بفرستید؛ مثال: government 500000',admin_menu()); return True
    if text in {'📊 گزارش','6'}:
        partners=db.conn.execute('SELECT COUNT(*) FROM partners').fetchone()[0]; requests=db.conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
        pending=db.conn.execute("SELECT COUNT(*) FROM requests WHERE payment_status='pending'").fetchone()[0]; topups=db.conn.execute("SELECT COUNT(*) FROM topups WHERE status='pending'").fetchone()[0]
        send(chat,f'📊 گزارش\n👥 همکاران: {partners}\n📋 درخواست‌ها: {requests}\n💳 پرداخت‌های معلق: {pending}\n💰 شارژهای در انتظار: {topups}',admin_menu()); return True
    if text in {'🚪 خروج از پنل','7'}:
        STATES[uid]['admin']=False; STATES[uid]['step']='menu'; send(chat,'✅ از پنل مدیریت خارج شدید.',main_menu(STATES[uid].get('lang','fa'))); return True
    m=re.fullmatch(r'تأیید شارژ #(\d+)',text)
    if m:
        tid=int(m.group(1)); row=db.conn.execute('SELECT * FROM topups WHERE id=?',(tid,)).fetchone()
        if row and row['status']=='pending':
            db.conn.execute("UPDATE topups SET status='approved',reviewed_at=? WHERE id=?",(now(),tid)); db.conn.execute('UPDATE partners SET balance=balance+?,updated_at=? WHERE id=?',(row['amount'],now(),row['partner_id'])); db.conn.commit()
        send(chat,f'✅ شارژ #{tid} بررسی شد.',admin_menu()); return True
    m=re.fullmatch(r'رد شارژ #(\d+)',text)
    if m:
        tid=int(m.group(1)); db.conn.execute("UPDATE topups SET status='rejected',reviewed_at=? WHERE id=? AND status='pending'",(now(),tid)); db.conn.commit(); send(chat,f'❌ شارژ #{tid} رد شد.',admin_menu()); return True
    m=re.fullmatch(r'تأیید پرداخت #(\d+)',text)
    if m:
        rid=int(m.group(1)); db.conn.execute("UPDATE requests SET payment_status='paid',status='submitted',updated_at=? WHERE id=? AND payment_status='pending'",(now(),rid)); db.conn.commit(); send(chat,f'✅ پرداخت #{rid} تأیید شد.',admin_menu()); return True
    m=re.fullmatch(r'رد پرداخت #(\d+)',text)
    if m:
        rid=int(m.group(1)); db.conn.execute("UPDATE requests SET payment_status='rejected',status='payment_rejected',updated_at=? WHERE id=? AND payment_status='pending'",(now(),rid)); db.conn.commit(); send(chat,f'❌ پرداخت #{rid} رد شد.',admin_menu()); return True
    if STATES.get(uid,{}).get('step')=='admin_price':
        a=text.split()
        if len(a)==2 and a[1].isdigit(): db.set_setting('price_'+a[0],int(a[1])); send(chat,'✅ قیمت ذخیره شد.',admin_menu()); STATES[uid]['step']='admin_menu'; return True
        send(chat,'❌ قالب نادرست است.',admin_menu()); return True
    return False

def call(method, payload=None):
    r=HTTP.post(f'{BASE}/{method}',json=payload or {},timeout=35); r.raise_for_status(); body=r.json()
    if isinstance(body,dict) and isinstance(body.get('data'),dict): return body['data']
    return body

def send(chat_id,text,keypad=None):
    payload={'chat_id':str(chat_id),'text':text}
    if keypad:
        payload['chat_keypad_type']='New'; payload['chat_keypad']={'rows':[{'buttons':[{'id':b[0],'type':'Simple','button_text':b[1]} for b in row]} for row in keypad],'resize_keyboard':True,'one_time_keyboard':False}
    last=None
    for attempt in range(3):
        try: return call('sendMessage',payload)
        except requests.RequestException as e: last=e; time.sleep(1.5*(attempt+1))
    raise last

def buttons(rows): return [[(str(i),label) for i,label in row] for row in rows]
def t(uid,key,**kw):
    lang=STATES.get(uid,{}).get('lang','fa'); return TEXT.get(lang,TEXT['fa'])[key].format(**kw)
def is_cancel(text): return text.strip() in {CANCEL,'انصراف','لغو','Cancel','cancel','إلغاء'}
def is_confirm(text): return text.strip() in {OK,'تأیید','تایید','Confirm','confirm','تأكيد'}

def main_menu(lang):
    if lang=='en': return buttons([[('1','🪪 FIDA non-in-person'),('2','🖨 Printing')],[('3','🏛 Government access issue'),('4','🎫 Tracking')],[('5','📱 SIM services'),('6','📝 Screening & follow-up')],[('7','💰 My wallet'),('8','👥 Partner panel')],[('9','📞 Contact us'),('0','❌ Cancel')]])
    if lang=='ar': return buttons([[('1','🪪 خدمة فيدا'),('2','🖨 الطباعة')],[('3','🏛 مشكلة خدمات الحكومة'),('4','🎫 متابعة')],[('5','📱 خدمات الشريحة'),('6','📝 الفحص والمتابعة')],[('7','💰 محفظتي'),('8','👥 لوحة الشركاء')],[('9','📞 اتصل بنا'),('0','❌ إلغاء')]])
    return buttons([[('1','🪪 فیدای غیر حضوری'),('2','🖨 خدمات چاپ')],[('3','🏛 حل مشکل ورود اتباع دولت من'),('4','🎫 پیگیری')],[('5','📱 خدمات سیم کارت'),('6','📝 آزمون غربالگری و پیگیری')],[('7','💰 کیف پول من'),('8','👥 پنل همکاران')],[('9','📞 تماس با ما'),('0',CANCEL)]])

def lang_menu(): return buttons([[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
def citizenship_menu(lang):
    if lang=='en': return buttons([[('1','🪪 Foreign national'),('2','🇮🇷 Iranian')]])
    if lang=='ar': return buttons([[('1','🪪 أجنبي'),('2','🇮🇷 إيراني')]])
    return buttons([[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')]])
def print_menu(lang):
    if lang=='en': return buttons([[('1','⚫ Black & white'),('2','🌈 Color')],[('0','❌ Cancel')]])
    if lang=='ar': return buttons([[('1','⚫ أبيض وأسود'),('2','🌈 ملون')],[('0','❌ إلغاء')]])
    return buttons([[('1','⚫ سیاه و سفید'),('2','🌈 رنگی')],[('0',CANCEL)]])
def side_menu(lang):
    if lang=='en': return buttons([[('1','📄 Single-sided'),('2','🔄 Double-sided')],[('0','❌ Cancel')]])
    if lang=='ar': return buttons([[('1','📄 وجه واحد'),('2','🔄 وجهان')],[('0','❌ إلغاء')]])
    return buttons([[('1','📄 یک‌رو'),('2','🔄 پشت‌ورو')],[('0',CANCEL)])])
def partner_menu(lang):
    if lang=='en': return buttons([[('1','➕ Top up'),('2','🔎 Track')],[('3','📋 History'),('4','💰 Balance')],[('0','❌ Cancel')]])
    if lang=='ar': return buttons([[('1','➕ شحن'),('2','🔎 متابعة')],[('3','📋 السجل'),('4','💰 الرصيد')],[('0','❌ إلغاء')]])
    return buttons([[('1','➕ شارژ حساب'),('2','🔎 پیگیری کد')],[('3','📋 سوابق'),('4','💰 موجودی')],[('0',CANCEL)]])
def normalize_lang_choice(text): return {'1':'fa','2':'en','3':'ar','فارسی':'fa','🇮🇷 فارسی':'fa','English':'en','🇬🇧 English':'en','العربية':'ar','🇸🇦 العربية':'ar'}.get(text.strip())
def message_payload(update):
    msg=update.get('new_message') or update.get('updated_message') or {}; return msg if isinstance(msg,dict) else {}
def sender_id(msg): return str(msg.get('sender_id') or msg.get('author_id') or '')
def message_text(msg):
    text=str(msg.get('text') or '').strip()
    if text: return text
    aux=msg.get('aux_data') or {}
    if isinstance(aux,dict):
        bid=aux.get('button_id') or aux.get('button_id_string')
        if bid is not None: return str(bid).strip()
    return ''
def media_id(msg):
    f=msg.get('file')
    if isinstance(f,dict) and f.get('file_id'): return str(f['file_id'])
    if msg.get('file_id'): return str(msg['file_id'])
    for key in ('photo','image','document','file'):
        v=msg.get(key)
        if isinstance(v,dict) and v.get('file_id'): return str(v['file_id'])
        if isinstance(v,str) and v: return v
    return ''
def new_state(uid): return STATES.setdefault(uid,{'lang':'fa','step':'language'})
def cancel(uid,chat):
    old=STATES.get(uid,{}); lang=old.get('lang','fa'); STATES[uid]={'lang':lang,'step':'menu','status':'foreign','partner_id':old.get('partner_id')}; send(chat,t(uid,'cancel'),main_menu(lang))
def create_request(uid,key,amount,platform='rubika'):
    internal=db.user(platform,uid,'',''); return db.create_request(internal,key,platform,amount)

# The remainder of the original request/media workflow is intentionally kept below unchanged.

def handle_text(uid,chat,text):
    st=new_state(uid); step=st.get('step'); lang=st.get('lang','fa')
    if text==ADMIN_COMMAND:
        STATES[uid]['admin']=True; STATES[uid]['step']='admin_menu'; send(chat,'🛠 پنل مدیریت کامل بات\nلطفاً گزینه موردنظر را انتخاب کنید:',admin_menu()); return
    if is_admin(uid) and STATES.get(uid,{}).get('admin'):
        if admin_action(uid,chat,text): return
    if is_cancel(text): cancel(uid,chat); return
    if step=='language':
        chosen=normalize_lang_choice(text)
        if not chosen: send(chat,TEXT['fa']['lang'],lang_menu()); return
        st['lang']=chosen; st['step']='citizenship'; send(chat,TEXT[chosen]['cit'],citizenship_menu(chosen)); return
    if step=='citizenship':
        if text in {'1','🪪 اتباع هستم','🪪 Foreign national','🪪 أجنبي'}: st['status']='foreign'; st['step']='menu'; send(chat,t(uid,'menu'),main_menu(lang)); return
        if text in {'2','🇮🇷 ایرانی هستم','🇮🇷 Iranian','🇮🇷 إيراني'}: st['status']='iranian'; st['step']='iranian_menu'; send(chat,t(uid,'iran'),buttons([[('1','👥 Partner panel'),('2','🎫 Track')],[('0','❌ Cancel')]])); return
        send(chat,t(uid,'bad'),citizenship_menu(lang)); return
    if step=='iranian_menu':
        if text in {'2','🎫 Track','🎫 پیگیری','🎫 متابعة'}: st['step']='track'; send(chat,t(uid,'track'),buttons([[('0','❌ Cancel')]])); return
        if text in {'1','👥 Partner panel','👥 پنل همکاران','👥 لوحة الشركاء'}: st['step']='partner_phone'; send(chat,t(uid,'login_phone'),buttons([[('0','❌ Cancel')]])); return
        send(chat,t(uid,'iran'),buttons([[('1','👥 Partner panel'),('2','🎫 Track')],[('0','❌ Cancel')]])); return
    if step=='menu':
        if text.startswith('1') or 'فیدا' in text.lower() or 'FIDA' in text or 'فيدا' in text: st['step']='fida_doc'; send(chat,t(uid,'fida'),buttons([[('0','❌ Cancel')]])); return
        if text.startswith('2') or 'چاپ' in text or 'Printing' in text or 'الطباعة' in text: st['step']='print_color'; send(chat,t(uid,'print'),print_menu(lang)); return
        if text.startswith('3') or 'دولت' in text or 'Government' in text or 'الحكومة' in text: st['step']='gov_fida'; send(chat,t(uid,'gov_fida'),buttons([[('0','❌ Cancel')]])); return
        if text.startswith('4') or 'پیگیری' in text or 'Tracking' in text or 'متابعة' in text: st['step']='track'; send(chat,t(uid,'track'),buttons([[('0','❌ Cancel')]])); return
        if text.startswith('7') or 'کیف پول' in text or 'wallet' in text.lower() or 'محفظ' in text:
            p=st.get('partner_id')
            if p:
                row=db.conn.execute('SELECT balance FROM partners WHERE id=?',(p,)).fetchone(); send(chat,t(uid,'balance',amount=int(row['balance']) if row else 0),main_menu(lang))
            else: send(chat,'💰 برای استفاده از کیف پول، ابتدا وارد پنل همکاران شوید.',main_menu(lang))
            return
        if text.startswith('8') or 'همکار' in text or 'Partner' in text or 'الشركاء' in text: st['step']='partner_phone'; send(chat,t(uid,'login_phone'),buttons([[('0','❌ Cancel')]])); return
        send(chat,t(uid,'menu'),main_menu(lang)); return
    if step=='track':
        row=db.conn.execute('SELECT * FROM requests WHERE tracking_code=?',(text,)).fetchone(); send(chat,(f"🎫 {row['tracking_code']}\n📌 وضعیت: {row['status']}\n💳 پرداخت: {row['payment_status']}\n💰 مبلغ: {row['amount']:,} تومان" if row else t(uid,'no_track')),main_menu(lang)); st['step']='menu'; return
    if step=='partner_phone':
        p=db.partner(text)
        if not p: send(chat,t(uid,'no_partner'),buttons([[('0','❌ Cancel')]])); return
        st['phone']=text; st['step']='partner_pass'; send(chat,t(uid,'login_pass'),buttons([[('0','❌ Cancel')]])); return
    if step=='partner_pass':
        p=db.partner(st.get('phone',''))
        if not p or not check_password(text,p['password_hash']): send(chat,t(uid,'bad_login'),buttons([[('0','❌ Cancel')]])); return
        st['partner_id']=p['id']; st['step']='partner_menu'; send(chat,t(uid,'balance',amount=int(p['balance'])),partner_menu(lang)); return
    if step=='partner_menu':
        if text.startswith('1') or 'شارژ' in text or 'Top up' in text or 'شحن' in text: st['step']='topup_amount'; send(chat,t(uid,'topup_amount'),buttons([[('0','❌ Cancel')]])); return
        if text.startswith('2') or 'پیگیری' in text or 'Track' in text or 'متابعة' in text: st['step']='partner_track'; send(chat,t(uid,'track'),buttons([[('0','❌ Cancel')]])); return
        if text.startswith('3') or 'سوابق' in text or 'History' in text or 'السجل' in text: rows=db.conn.execute('SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20',(st['partner_id'],)).fetchall(); send(chat,'\n'.join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,}" for r in rows) or 'سابقه‌ای نیست.',partner_menu(lang)); return
        if text.startswith('4') or 'موجودی' in text or 'Balance' in text or 'الرصيد' in text: p=db.conn.execute('SELECT balance FROM partners WHERE id=?',(st['partner_id'],)).fetchone(); send(chat,t(uid,'balance',amount=int(p['balance']) if p else 0),partner_menu(lang)); return
        send(chat,t(uid,'bad'),partner_menu(lang)); return
    if step=='partner_track':
        row=db.conn.execute('SELECT * FROM requests WHERE tracking_code=? AND user_id=?',(text,st['partner_id'])).fetchone(); send(chat,(f"🎫 {row['tracking_code']}\n📌 وضعیت: {row['status']}\n💰 مبلغ: {row['amount']:,} تومان" if row else t(uid,'no_track')),partner_menu(lang)); st['step']='partner_menu'; return
    if step=='topup_amount':
        try: amount=int(re.sub(r'[^\d]','',text))
        except: amount=0
        if amount<=0: send(chat,t(uid,'topup_amount'),buttons([[('0','❌ Cancel')]])); return
        st['topup_amount']=amount; st['step']='topup_receipt'; send(chat,f"💳 {amount:,} تومان\nکارت: {db.setting('card_number')}\nبه نام: {db.setting('card_owner')}\n\n"+t(uid,'topup_receipt'),buttons([[('0','❌ Cancel')]])); return
    if step=='gov_fida': st['fida_id']=text; st['step']='gov_yekta'; send(chat,t(uid,'gov_yekta'),buttons([[('0','❌ Cancel')]])); return
    if step=='gov_yekta': st['yekta']=text; st['step']='gov_id'; send(chat,t(uid,'id'),buttons([[('0','❌ Cancel')]])); return
    if step=='gov_sim' and text in {'ندارم','No','No document','لا يوجد'}: st['sim_document']=''; st['step']='gov_phone'; send(chat,t(uid,'phone'),buttons([[('0','❌ Cancel')]])); return
    if step=='gov_phone': st['phone']=text; st['step']='gov_dob'; send(chat,t(uid,'dob'),buttons([[('0','❌ Cancel')]])); return
    if step=='gov_dob':
        if not re.fullmatch(r'1[34]\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])',text): send(chat,t(uid,'dob'),buttons([[('0','❌ Cancel')]])); return
        st['dob']=text; st['step']='gov_doc'; send(chat,t(uid,'doc'),buttons([[('1','ندارم')],[('0','❌ Cancel')]])); return
    if step=='print_color':
        if text.startswith('1'): st['color']='bw'
        elif text.startswith('2'): st['color']='color'
        else: send(chat,t(uid,'print'),print_menu(lang)); return
        st['step']='print_side'; send(chat,t(uid,'side'),side_menu(lang)); return
    if step=='print_side':
        if text.startswith('1'): st['side']='single'
        elif text.startswith('2'): st['side']='double'
        else: send(chat,t(uid,'side'),side_menu(lang)); return
        st['step']='print_copies'; send(chat,t(uid,'copies'),buttons([[('0','❌ Cancel')]])); return
    if step=='print_copies':
        if not text.isdigit() or int(text)<1: send(chat,t(uid,'copies'),buttons([[('0','❌ Cancel')]])); return
        st['copies']=int(text); st['step']='print_files'; st['files']=[]; send(chat,t(uid,'files'),buttons([[('1',OK)],[('0','❌ Cancel')]])); return
    send(chat,t(uid,'bad'))

def handle_media(uid,chat,msg):
    fid=media_id(msg)
    if not fid: send(chat,t(uid,'bad')); return
    st=new_state(uid); step=st.get('step')
    if step=='fida_doc': st['doc']=fid; st['step']='fida_phone'; send(chat,t(uid,'fida_phone'),buttons([[('0','❌ Cancel')]])); return
    if step=='gov_id': st['id_document']=fid; st['step']='gov_sim'; send(chat,t(uid,'doc'),buttons([[('1','ندارم')],[('0','❌ Cancel')]])); return
    if step=='gov_sim': st['sim_document']=fid; st['step']='gov_phone'; send(chat,t(uid,'phone'),buttons([[('0','❌ Cancel')]])); return
    if step=='topup_receipt': tid=db.add_topup(st['partner_id'],int(st['topup_amount']),fid); st['step']='partner_menu'; send(chat,t(uid,'topup_sent',id=tid),partner_menu(st.get('lang','fa'))); return
    if step=='print_files': st.setdefault('files',[]).append(fid); send(chat,t(uid,'received'),buttons([[('1',OK)],[('0','❌ Cancel')]])); return
    if step=='payment_receipt':
        rid=int(st['rid']); db.conn.execute("UPDATE requests SET payment_status='pending',status='payment_review',payment_note=?,updated_at=? WHERE id=?",(fid,now(),rid)); db.conn.commit(); st['step']='menu'; send(chat,'✅ رسید دریافت شد و برای بررسی مدیر ارسال شد.',main_menu(st.get('lang','fa'))); return
    send(chat,t(uid,'bad'))

def process_update(update):
    if not isinstance(update,dict): return
    chat=str(update.get('chat_id') or '')
    msg=message_payload(update); sender=sender_id(msg)
    if not chat: return
    # Session state is keyed by chat_id, which is stable for the conversation.
    # This prevents a missing/changed sender_id from resetting the language flow.
    uid=chat
    if msg.get('sender_type')=='Bot': return
    db.user('rubika',sender or chat,'',str(msg.get('first_name') or msg.get('username') or ''))
    if update.get('type')=='StartedBot':
        if uid not in STATES: STATES[uid]={'lang':'fa','step':'language'}
        send(chat,TEXT['fa']['lang'],lang_menu()); return
    text=message_text(msg)
    if text=='/start':
        STATES[uid]={'lang':'fa','step':'language'}; send(chat,TEXT['fa']['lang'],lang_menu()); return
    if text and is_cancel(text): cancel(uid,chat); return
    if media_id(msg): handle_media(uid,chat,msg); return
    handle_text(uid,chat,text)

def run():
    try:
        me=call('getMe'); log.info('Rubika getMe OK: %s',me)
    except Exception: log.exception('Rubika getMe failed'); raise
    offset=None; log.info('NetYar Rubika long-polling started')
    while True:
        try:
            payload={'limit':20}
            if offset: payload['offset_id']=offset
            data=call('getUpdates',payload)
            if isinstance(data,list): updates=data; nxt=None
            else: updates=(data or {}).get('updates',[]) or []; nxt=(data or {}).get('next_offset_id')
            for upd in updates:
                try: process_update(upd)
                except Exception: log.exception('Rubika update failed')
            if nxt: offset=str(nxt)
            time.sleep(0.8)
        except requests.RequestException:
            log.exception('Rubika API/network error'); time.sleep(5)
        except Exception:
            log.exception('Rubika loop error'); time.sleep(5)

if __name__=='__main__': run()
