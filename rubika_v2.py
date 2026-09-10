import os, time, logging, re, json, requests
from core import db, now, check_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("netyar.rubika.v2")
TOKEN = os.getenv("RUBIKA_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("RUBIKA_BOT_TOKEN is missing")
BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"
HTTP = requests.Session()
HTTP.headers.update({"Content-Type": "application/json"})
ADMIN_IDS = {x.strip() for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip()}
ADMIN_COMMAND = os.getenv("ADMIN_COMMAND", "/Admin2025").strip()
CANCEL, OK = "❌ انصراف", "✅ تأیید"
STATE, OFFSET = {}, None
TEXT = {
 "fa":{"lang":"🌐 زبان را انتخاب کنید:","cit":"آیا اتباع هستید یا ایرانی؟","iran":"🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.","menu":"سلام 👋\nبه «کمک یار مهاجر» خوش آمدید.\nخدمت موردنظر را انتخاب کنید:","phone":"📱 شماره موبایل مشترک را وارد کنید.","partner_phone":"📱 شماره همراه همکار را وارد کنید.","partner_pass":"🔐 رمز عبور همکار را وارد کنید.","bad_login":"❌ شماره همراه یا رمز عبور نادرست است.","no_partner":"❌ همکار پیدا نشد.","balance":"💰 موجودی اعتبار: {amount:,} تومان","track":"🎫 کد پیگیری را وارد کنید.","not_found":"❌ کد پیگیری پیدا نشد.","cancel":"عملیات لغو شد. به منوی اصلی برگشتید. ✅","bad":"لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.","fida":"🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.","gov_fida":"🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید.","gov_yekta":"🔢 شناسه یکتای مشترک را وارد کنید.","dob":"🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.","print":"🖨 نوع چاپ را انتخاب کنید:","copies":"🔢 تعداد نسخه از هر صفحه را وارد کنید.","files":"📎 عکس‌ها یا فایل‌ها را یکی‌یکی ارسال کنید. در پایان «تأیید» را بزنید.","received":"✅ دریافت شد. مورد بعدی را بفرستید یا «تأیید» را بزنید.","need_balance":"❌ اعتبار کافی نیست. لطفاً ابتدا حساب را شارژ کنید.","payment":"🧾 درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان","admin":"🛠 پنل مدیریت کامل\nگزینه موردنظر را انتخاب کنید:","bot_platform":"پیام‌رسان را انتخاب کنید:","bot_name":"🤖 نام بات را وارد کنید:","bot_api":"🔑 API را ارسال کنید:","bot_saved":"✅ بات {name} برای {platform} ثبت شد.","status":"📌 وضعیت: {status}\n🎫 کد: {code}\n💰 مبلغ: {amount:,} تومان"},
 "en":{"lang":"🌐 Choose your language:","cit":"Are you a foreign national or Iranian?","iran":"🇮🇷 Services are currently unavailable for Iranian users.","menu":"Hello 👋\nWelcome to Mohajer Helper.\nChoose a service:","phone":"📱 Enter customer's mobile number.","partner_phone":"📱 Enter partner phone:","partner_pass":"🔐 Enter partner password:","bad_login":"❌ Invalid phone or password.","no_partner":"❌ Partner not found.","balance":"💰 Balance: {amount:,} toman","track":"🎫 Enter tracking code.","not_found":"❌ Tracking code not found.","cancel":"Operation cancelled. Back to main menu. ✅","bad":"Please choose one of the displayed options.","fida":"🪪 Send the customer's ID document.","gov_fida":"🆔 Enter customer's FIDA/special ID.","gov_yekta":"🔢 Enter customer's unique ID.","dob":"🎂 Enter customer's birth date as 1356/01/01.","print":"🖨 Choose print type:","copies":"🔢 Enter copies per page.","files":"📎 Send files/images one by one. Press Confirm when finished.","received":"✅ Received. Send another item or press Confirm.","need_balance":"❌ Insufficient balance. Please top up first.","payment":"🧾 Request created.\n🎫 Tracking: {code}\n💰 Amount: {amount:,} toman","admin":"🛠 Full admin panel\nChoose an option:","bot_platform":"Choose messenger:","bot_name":"🤖 Enter bot name:","bot_api":"🔑 Send API token:","bot_saved":"✅ Bot {name} for {platform} was saved.","status":"📌 Status: {status}\n🎫 Code: {code}\n💰 Amount: {amount:,} toman"},
 "ar":{"lang":"🌐 اختر اللغة:","cit":"هل أنت من الرعايا الأجانب أم إيراني؟","iran":"🇮🇷 الخدمات غير متاحة حالياً للمستخدمين الإيرانيين.","menu":"مرحباً 👋\nأهلاً بك في مساعد المهاجر.\nاختر الخدمة:","phone":"📱 أدخل رقم هاتف العميل.","partner_phone":"📱 أدخل رقم هاتف الشريك:","partner_pass":"🔐 أدخل كلمة مرور الشريك:","bad_login":"❌ رقم الهاتف أو كلمة المرور غير صحيحة.","no_partner":"❌ لم يتم العثور على الشريك.","balance":"💰 الرصيد: {amount:,} تومان","track":"🎫 أدخل رمز المتابعة.","not_found":"❌ لم يتم العثور على الرمز.","cancel":"تم إلغاء العملية والعودة إلى القائمة الرئيسية. ✅","bad":"يرجى اختيار أحد الخيارات المعروضة.","fida":"🪪 أرسل صورة وثيقة هوية العميل.","gov_fida":"🆔 أدخل رقم فيدا/الرقم الخاص بالعميل.","gov_yekta":"🔢 أدخل المعرف الفريد للعميل.","dob":"🎂 أدخل تاريخ الميلاد بالشكل 1356/01/01.","print":"🖨 اختر نوع الطباعة:","copies":"🔢 أدخل عدد النسخ لكل صفحة.","files":"📎 أرسل الملفات أو الصور. عند الانتهاء اختر تأكيد.","received":"✅ تم الاستلام. أرسل المزيد أو اختر تأكيد.","need_balance":"❌ الرصيد غير كافٍ. يرجى شحن الحساب أولاً.","payment":"🧾 تم إنشاء الطلب.\n🎫 رمز المتابعة: {code}\n💰 المبلغ: {amount:,} تومان","admin":"🛠 لوحة الإدارة الكاملة\nاختر خياراً:","bot_platform":"اختر تطبيق المراسلة:","bot_name":"🤖 أدخل اسم البوت:","bot_api":"🔑 أرسل رمز API:","bot_saved":"✅ تم حفظ البوت {name} لمنصة {platform}.","status":"📌 الحالة: {status}\n🎫 الرمز: {code}\n💰 المبلغ: {amount:,} تومان"}}

def lang(uid): return STATE.get(str(uid),{}).get("lang","fa")
def T(uid,k,**kw): return TEXT[lang(uid)].get(k,TEXT["fa"].get(k,k)).format(**kw)
def rows(r): return [{"buttons":[{"id":str(i),"type":"Simple","button_text":str(label)} for i,label in row]} for row in r]
def send(chat,text,r=None):
    p={"chat_id":str(chat),"text":text}
    if r: p.update(chat_keypad_type="New",chat_keypad={"rows":rows(r),"resize_keyboard":True,"one_time_keyboard":False})
    for n in range(3):
        try:
            z=HTTP.post(f"{BASE}/sendMessage",json=p,timeout=30); z.raise_for_status(); return z.json()
        except requests.RequestException:
            if n==2: raise
            time.sleep(n+1)
def call(method,p=None):
    z=HTTP.post(f"{BASE}/{method}",json=p or {},timeout=35); z.raise_for_status(); d=z.json()
    if isinstance(d,dict) and d.get("status") not in (None,"OK"): raise RuntimeError(str(d))
    return d.get("data",d) if isinstance(d,dict) else d
def text_of(u):
    m=u.get("message") or u.get("new_message") or u
    if not isinstance(m,dict): return ""
    for k in ("text","button_text"):
        if m.get(k): return str(m[k]).strip()
    a=m.get("aux_data")
    if isinstance(a,dict): return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip()
    if isinstance(a,str):
        try:
            a=json.loads(a); return str(a.get("button_id") or a.get("button_text") or a.get("text") or "").strip() if isinstance(a,dict) else ""
        except Exception: return ""
    return ""
def chat_of(u):
    # Rubika NewMessage webhooks put chat_id on the update itself, while
    # sender_id/text/aux_data live inside new_message.
    if isinstance(u,dict) and u.get("chat_id"):
        return str(u.get("chat_id"))
    m=u.get("message") or u.get("new_message") or u
    return str((m or {}).get("chat_id") or (m or {}).get("chat_key") or "")
def user_of(u):
    m=u.get("message") or u.get("new_message") or u; s=(m or {}).get("sender") or {}
    return str((s or {}).get("user_id") or (m or {}).get("sender_id") or (m or {}).get("user_id") or chat_of(u))
def file_of(u):
    m=u.get("message") or u.get("new_message") or u
    f=(m or {}).get("file") or {}
    return str(f.get("file_id") or (m or {}).get("file_id") or "")
def main_rows(uid):
    l=lang(uid)
    if l=="en": return [[("1","🪪 FIDA non-in-person"),("2","🖨 Printing")],[("3","🏛 Government access issue"),("4","🎫 Tracking")],[("5","📱 SIM services"),("6","📝 Screening & follow-up")],[("7","💰 My wallet"),("8","👥 Partner panel")],[("9","📞 Contact us"),("0","❌ Cancel")]]
    if l=="ar": return [[("1","🪪 خدمة فيدا"),("2","🖨 الطباعة")],[("3","🏛 مشكلة خدمات الحكومة"),("4","🎫 متابعة")],[("5","📱 خدمات الشريحة"),("6","📝 الفحص والمتابعة")],[("7","💰 محفظتي"),("8","👥 لوحة الشركاء")],[("9","📞 اتصل بنا"),("0","❌ إلغاء")]]
    return [[("1","🪪 فیدای غیر حضوری"),("2","🖨 خدمات چاپ")],[("3","🏛 حل مشکل ورود اتباع دولت من"),("4","🎫 پیگیری")],[("5","📱 خدمات سیم کارت"),("6","📝 آزمون غربالگری و پیگیری")],[("7","💰 کیف پول من"),("8","👥 پنل همکاران")],[("9","📞 تماس با ما"),("0",CANCEL)]]
def partner_rows(): return [[("1","➕ شارژ حساب"),("2","🔎 پیگیری کد")],[("3","📋 سوابق"),("4","💰 موجودی")],[("5","🏛 حل مشکل سامانه دولت من")],[("0",CANCEL)]]
def admin_rows(): return [[("1","👥 همکاران"),("2","💰 شارژها")],[("3","📋 درخواست‌ها"),("4","💳 پرداخت‌ها")],[("5","⚙️ قیمت‌ها"),("6","🤖 افزودن بات")],[("7","🤖 بات‌های متصل"),("8","📊 گزارش")],[("0","⬅️ منوی اصلی")]]
def is_admin(uid): return str(uid) in ADMIN_IDS or STATE.get(str(uid),{}).get("admin") is True
def notify_admins(s):
    for a in ADMIN_IDS:
        try: send(a,s,admin_rows())
        except Exception: pass

def cancel(uid,chat):
    st=STATE.setdefault(str(uid),{"lang":"fa"}); st.update({"step":"citizenship","admin":False}); send(chat,T(uid,"cit"),[[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')]])

def admin(uid,chat,x):
    st=STATE[str(uid)]; step=st.get("step")
    if step=="admin_price":
        a=x.split()
        if len(a)==2 and a[1].isdigit(): db.set_setting(a[0],a[1]); st["step"]="admin"; send(chat,"✅ قیمت ذخیره شد.",admin_rows()); return
        send(chat,"❌ قالب: price_government 500000"); return
    if step=="bot_platform":
        p={"1":"telegram","2":"rubika","3":"bale","4":"eitaa"}.get(x)
        if p: st["bot_platform"]=p; st["step"]="bot_name"; send(chat,T(uid,"bot_name")); return
        send(chat,"❌ گزینه نامعتبر."); return
    if step=="bot_name": st["bot_name"]=x; st["step"]="bot_api"; send(chat,T(uid,"bot_api")); return
    if step=="bot_api":
        p=st.get("bot_platform"); name=st.get("bot_name") or p
        db.set_setting(f"bot_{p}_name",name); db.set_setting(f"bot_{p}_api",x); st["step"]="admin"; send(chat,T(uid,"bot_saved",name=name,platform=p),admin_rows()); return
    if step=="admin":
        if x=="1": rows0=db.conn.execute("SELECT phone, balance, active FROM partners ORDER BY phone").fetchall(); txt="👥 همکاران\n"+"\n".join(f"{r[0]} | {r[1]:,} | {'فعال' if r[2] else 'غیرفعال'}" for r in rows0) if rows0 else "👥 هنوز همکاری ثبت نشده."; send(chat,txt,admin_rows()); return
        if x=="2": rows0=db.conn.execute("SELECT id, partner_phone, amount, status FROM topups ORDER BY id DESC LIMIT 20").fetchall(); txt="💰 شارژها\n"+"\n".join(f"#{r[0]} | {r[1]} | {r[2]:,} | {r[3]}" for r in rows0) if rows0 else "💰 شارژی ثبت نشده."; send(chat,txt,admin_rows()); return
        if x=="3": rows0=db.conn.execute("SELECT code, service_key, amount, status FROM requests ORDER BY id DESC LIMIT 20").fetchall(); txt="📋 درخواست‌ها\n"+"\n".join(f"{r[0]} | {r[1]} | {r[2]:,} | {r[3]}" for r in rows0) if rows0 else "📋 درخواستی ثبت نشده."; send(chat,txt,admin_rows()); return
        if x=="4": rows0=db.conn.execute("SELECT code, amount, status FROM requests ORDER BY id DESC LIMIT 20").fetchall(); txt="💳 پرداخت‌ها\n"+"\n".join(f"{r[0]} | {r[1]:,} | {r[2]}" for r in rows0) if rows0 else "💳 پرداختی ثبت نشده."; send(chat,txt,admin_rows()); return
        if x=="5": st["step"]="admin_price"; send(chat,"⚙️ قیمت را به شکل زیر بفرست:\nprice_government 500000"); return
        if x=="6": st["step"]="bot_platform"; send(chat,T(uid,"bot_platform"),[[('1','Telegram'),('2','Rubika'),('3','Bale'),('4','Eitaa')]]); return
        if x=="7": rows0=db.conn.execute("SELECT key, value FROM settings WHERE key LIKE 'bot_%_name' ORDER BY key").fetchall(); txt="🤖 بات‌های متصل\n"+"\n".join(f"{r[0]}: {r[1]}" for r in rows0) if rows0 else "🤖 باتی ثبت نشده."; send(chat,txt,admin_rows()); return
        if x=="8":
            pc=db.conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0]; rc=db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]; tc=db.conn.execute("SELECT COUNT(*) FROM topups WHERE status='pending'").fetchone()[0]; send(chat,f"📊 گزارش\n👥 {pc}\n📋 {rc}\n💰 شارژهای در انتظار: {tc}",admin_rows()); return
    send(chat,T(uid,"admin"),admin_rows())

def handle(uid,chat,x,u):
    uid=str(uid); st=STATE.setdefault(uid,{"lang":"fa","step":"language"})
    if x.startswith("/start"): STATE[uid]={"lang":"fa","step":"language"}; send(chat,TEXT["fa"]["lang"],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]]); return
    if x==ADMIN_COMMAND: st["admin"]=True; st["step"]="admin"; send(chat,T(uid,"admin"),admin_rows()); return
    if x in {CANCEL,"0","انصراف","لغو","Cancel","cancel","إلغاء"}: cancel(uid,chat); return
    step=st.get("step")
    if st.get("admin") and step in {"admin","admin_price","bot_platform","bot_name","bot_api"}: admin(uid,chat,x); return
    if step=="language":
        z={"1":"fa","2":"en","3":"ar","🇮🇷 فارسی":"fa","🇬🇧 English":"en","🇸🇦 العربية":"ar","فارسی":"fa","English":"en","العربية":"ar"}.get(x)
        if not z: send(chat,TEXT["fa"]["lang"],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]]); return
        st["lang"]=z; st["step"]="citizenship"; l=z; cr=[[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')] if l=='fa' else [('1','🪪 Foreign national'),('2','🇮🇷 Iranian')] if l=='en' else [('1','🪪 أجنبي'),('2','🇮🇷 إيراني')]]; send(chat,T(uid,"cit"),cr); return
    if step=="citizenship":
        if x in {"1","🪪 اتباع هستم","🪪 Foreign national","🪪 أجنبي"}: st["step"]="main"; send(chat,T(uid,"menu"),main_rows(uid)); return
        if x in {"2","🇮🇷 ایرانی هستم","🇮🇷 Iranian","🇮🇷 إيراني"}: send(chat,T(uid,"iran")); return
    if step in {"main","service"}:
        if x in {"1","🪪 فیدای غیر حضوری","🪪 FIDA non-in-person","🪪 خدمة فيدا"}: st["step"]="fida_phone"; send(chat,T(uid,"phone")); return
        if x in {"2","🖨 خدمات چاپ","🖨 Printing","🖨 الطباعة"}: st["step"]="print"; send(chat,T(uid,"print"),[[('1','🖨 سیاه و سفید'),('2','🎨 رنگی')]]); return
        if x in {"3","🏛 حل مشکل ورود اتباع دولت من","🏛 Government access issue","🏛 مشكلة خدمات الحكومة"}: st["step"]="gov_doc"; send(chat,"📄 نوع مدرک را انتخاب کنید:",[[('1','کارت آمایش'),('2','کارت موقت')],[('3','پاسپورت'),('4','دفترچه اقامت')]]); return
        if x in {"4","🎫 پیگیری","🎫 Tracking","🎫 متابعة"}: st["step"]="track"; send(chat,T(uid,"track")); return
        if x in {"5","📱 خدمات سیم کارت","📱 SIM services","📱 خدمات الشريحة"}: st["step"]="sim"; send(chat,"📱 خدمات سیم کارت در حال تکمیل است."); return
        if x in {"6","📝 آزمون غربالگری و پیگیری","📝 Screening & follow-up","📝 الفحص والمتابعة"}: st["step"]="screening"; send(chat,"📝 آزمون غربالگری را انتخاب کردید."); return
        if x in {"7","💰 کیف پول من","💰 My wallet","💰 محفظتي"}: send(chat,T(uid,"balance",amount=db.get_balance(uid)),main_rows(uid)); return
        if x in {"8","👥 پنل همکاران","👥 Partner panel","👥 لوحة الشركاء"}: st["step"]="partner_phone"; send(chat,T(uid,"partner_phone")); return
        if x in {"9","📞 تماس با ما","📞 Contact us","📞 اتصل بنا"}: send(chat,"📞 تماس با ما: لطفاً با پشتیبانی نت‌یار مهاجر در ارتباط باشید.",main_rows(uid)); return
        send(chat,T(uid,"bad"),main_rows(uid)); return
    if step=="partner_phone":
        if x in {CANCEL,"0"}: cancel(uid,chat); return
        st["partner_phone"]=x; st["step"]="partner_pass"; send(chat,T(uid,"partner_pass")); return
    if step=="partner_pass":
        phone=st.get("partner_phone"); p=db.get_partner(phone)
        if not p or not check_password(p["password"],x): st["step"]="partner_phone"; send(chat,T(uid,"bad_login")); return
        st["partner"]=phone; st["step"]="partner"; send(chat,f"👥 پنل همکار\n{T(uid,'balance',amount=db.get_balance(phone))}",partner_rows()); return
    if step=="partner":
        if x=="1": st["step"]="topup_amount"; send(chat,"💰 مبلغ شارژ را به تومان وارد کنید."); return
        if x=="2": st["step"]="track"; send(chat,T(uid,"track")); return
        if x=="3": send(chat,"📋 سوابق همکار فعلاً محدود به درخواست‌های اخیر است.",partner_rows()); return
        if x=="4": send(chat,T(uid,"balance",amount=db.get_balance(st.get("partner"))),partner_rows()); return
        if x=="5": st["step"]="gov_doc"; send(chat,"📄 نوع مدرک را انتخاب کنید:",[[('1','کارت آمایش'),('2','کارت موقت')],[('3','پاسپورت'),('4','دفترچه اقامت')]]); return
        send(chat,T(uid,"bad"),partner_rows()); return
    if step=="topup_amount":
        if not x.isdigit(): send(chat,"❌ فقط عدد وارد کنید."); return
        st["topup_amount"]=int(x); st["step"]="topup_receipt"; send(chat,"🧾 تصویر رسید واریز را ارسال کنید."); return
    if step=="topup_receipt":
        f=file_of(u)
        if not f: send(chat,"📎 لطفاً تصویر رسید را ارسال کنید."); return
        amount=st.get("topup_amount",0); db.create_topup(st.get("partner"),amount,f); st["step"]="partner"; notify_admins(f"💰 شارژ جدید\n👥 {st.get('partner')}\n💵 {amount:,} تومان\n🧾 رسید: {f}"); send(chat,"✅ رسید ثبت شد و برای تأیید مدیریت ارسال شد.",partner_rows()); return
    if step=="track":
        q=db.get_request(x)
        if not q: send(chat,T(uid,"not_found")); return
        send(chat,T(uid,"status",status=q["status"],code=q["code"],amount=q["amount"])); return
    if step=="fida_phone":
        st["customer_phone"]=x; st["step"]="fida_file"; send(chat,T(uid,"fida")); return
    if step=="fida_file":
        f=file_of(u)
        if not f: send(chat,"📎 لطفاً تصویر مدرک را ارسال کنید."); return
        st["fida_file"]=f; st["step"]="main"; amount=int(db.get_setting("price_fida", "0") or 0); pid=st.get("partner");
        if pid and db.get_balance(pid)<amount: send(chat,T(uid,"need_balance"),partner_rows()); return
        code=db.create_request(pid,uid,"fida",amount,f); send(chat,T(uid,"payment",code=code,amount=amount),partner_rows() if pid else main_rows(uid)); notify_admins(f"🔔 درخواست جدید\n🎫 {code}\n🧩 fida\n💰 {amount:,} تومان"); return
    if step=="print":
        if x in {"1","🖨 سیاه و سفید"}: st["print_type"]="bw"; st["step"]="copies"; send(chat,T(uid,"copies")); return
        if x in {"2","🎨 رنگی"}: st["print_type"]="color"; st["step"]="copies"; send(chat,T(uid,"copies")); return
        send(chat,T(uid,"bad"),[[('1','🖨 سیاه و سفید'),('2','🎨 رنگی')]]); return
    if step=="copies":
        if not x.isdigit(): send(chat,"❌ تعداد نسخه را عددی وارد کنید."); return
        st["copies"]=int(x); st["step"]="print_files"; send(chat,T(uid,"files"),[[('1',OK),('0',CANCEL)]]); return
    if step=="print_files":
        if x in {OK,"1"}:
            files=st.get("files",[]); amount=int(db.get_setting("price_print", "0") or 0)*max(1,st.get("copies",1))*max(1,len(files)); pid=st.get("partner");
            if pid and db.get_balance(pid)<amount: send(chat,T(uid,"need_balance"),partner_rows()); return
            code=db.create_request(pid,uid,"print",amount,",".join(files)); st["step"]="main"; send(chat,T(uid,"payment",code=code,amount=amount),partner_rows() if pid else main_rows(uid)); notify_admins(f"🔔 درخواست چاپ\n🎫 {code}\n💰 {amount:,} تومان"); return
        f=file_of(u)
        if f: st.setdefault("files",[]).append(f); send(chat,T(uid,"received")); return
        send(chat,T(uid,"files"),[[('1',OK),('0',CANCEL)]]); return
    if step=="gov_doc":
        docs={"1":"amaysh","2":"temporary","3":"passport","4":"residence"}
        if x not in docs: send(chat,"❌ نوع مدرک را انتخاب کنید."); return
        st["gov_doc"]=docs[x]; st["step"]="gov_files"; send(chat,"📸 تصاویر مدرک را ارسال کنید. برای پاسپورت: صفحه اول و صفحه تمدید را بفرستید.",[[('1',OK),('0',CANCEL)]]); return
    if step=="gov_files":
        if x in {OK,"1"}:
            files=st.get("files",[])
            if not files: send(chat,"❌ حداقل یک تصویر ارسال کنید."); return
            amount=int(db.get_setting("price_government", "0") or 0); pid=st.get("partner");
            if pid and db.get_balance(pid)<amount: send(chat,T(uid,"need_balance"),partner_rows()); return
            code=db.create_request(pid,uid,"government",amount,",".join(files)); st["step"]="main"; send(chat,T(uid,"payment",code=code,amount=amount),partner_rows() if pid else main_rows(uid)); notify_admins(f"🏛 درخواست دولت من\n🎫 {code}\n📄 {st.get('gov_doc')}\n💰 {amount:,} تومان"); return
        f=file_of(u)
        if f: st.setdefault("files",[]).append(f); send(chat,T(uid,"received")); return
        send(chat,"📸 تصویر مدرک را ارسال کنید یا تأیید را بزنید.",[[('1',OK),('0',CANCEL)]]); return
    if step=="screening": send(chat,"📝 آزمون غربالگری ثبت شد.",main_rows(uid)); st["step"]="main"; return
    send(chat,T(uid,"bad"),main_rows(uid))


def process(u):
    uid=user_of(u); chat=chat_of(u); x=text_of(u); handle(uid,chat,x,u)
