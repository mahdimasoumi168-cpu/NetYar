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
RESTART = "🔄 شروع مجدد"
STATE, OFFSET = {}, None
TEXT = {
 "fa":{"lang":"🌐 زبان را انتخاب کنید:","cit":"آیا اتباع هستید یا ایرانی؟","iran":"🇮🇷 خدمات ایرانی را انتخاب کنید:","menu":"سلام 👋\nبه «کمک یار مهاجر» خوش آمدید.\nخدمت موردنظر را انتخاب کنید:","phone":"📱 شماره موبایل مشترک را وارد کنید.","partner_phone":"📱 شماره همراه همکار را وارد کنید.","partner_pass":"🔐 رمز عبور همکار را وارد کنید.","bad_login":"❌ شماره همراه یا رمز عبور نادرست است.","no_partner":"❌ همکار پیدا نشد.","balance":"💰 موجودی اعتبار: {amount:,} تومان","track":"🎫 کد پیگیری را وارد کنید.","not_found":"❌ کد پیگیری پیدا نشد.","cancel":"عملیات لغو شد. به منوی اصلی برگشتید. ✅","bad":"لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.","fida":"🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.","gov_fida":"🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید.","gov_yekta":"🔢 شناسه یکتای مشترک را وارد کنید.","dob":"🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.","print":"🖨 نوع چاپ را انتخاب کنید:","copies":"🔢 تعداد نسخه از هر صفحه را وارد کنید.","files":"📎 عکس‌ها یا فایل‌ها را یکی‌یکی ارسال کنید. در پایان «تأیید» را بزنید.","received":"✅ دریافت شد. مورد بعدی را بفرستید یا «تأیید» را بزنید.","need_balance":"❌ اعتبار کافی نیست. لطفاً ابتدا حساب را شارژ کنید.","payment":"🧾 درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان","admin":"🛠 پنل مدیریت کامل\nگزینه موردنظر را انتخاب کنید:","bot_platform":"پیام‌رسان را انتخاب کنید:","bot_name":"🤖 نام بات را وارد کنید:","bot_api":"🔑 API را ارسال کنید:","bot_saved":"✅ بات {name} برای {platform} ثبت شد.","status":"📌 وضعیت: {status}\n🎫 کد: {code}\n💰 مبلغ: {amount:,} تومان"},
 "en":{"lang":"🌐 Choose your language:","cit":"Are you a foreign national or Iranian?","iran":"🇮🇷 Choose an Iranian service:","menu":"Hello 👋\nWelcome to Mohajer Helper.\nChoose a service:","phone":"📱 Enter customer's mobile number.","partner_phone":"📱 Enter partner phone:","partner_pass":"🔐 Enter partner password:","bad_login":"❌ Invalid phone or password.","no_partner":"❌ Partner not found.","balance":"💰 Balance: {amount:,} toman","track":"🎫 Enter tracking code.","not_found":"❌ Tracking code not found.","cancel":"Operation cancelled. Back to main menu. ✅","bad":"Please choose one of the displayed options.","fida":"🪪 Send the customer's ID document.","gov_fida":"🆔 Enter customer's FIDA/special ID.","gov_yekta":"🔢 Enter customer's unique ID.","dob":"🎂 Enter customer's birth date as 1356/01/01.","print":"🖨 Choose print type:","copies":"🔢 Enter copies per page.","files":"📎 Send files/images one by one. Press Confirm when finished.","received":"✅ Received. Send another item or press Confirm.","need_balance":"❌ Insufficient balance. Please top up first.","payment":"🧾 Request created.\n🎫 Tracking: {code}\n💰 Amount: {amount:,} toman","admin":"🛠 Full admin panel\nChoose an option:","bot_platform":"Choose messenger:","bot_name":"🤖 Enter bot name:","bot_api":"🔑 Send API token:","bot_saved":"✅ Bot {name} for {platform} was saved.","status":"📌 Status: {status}\n🎫 Code: {code}\n💰 Amount: {amount:,} toman"},
 "ar":{"lang":"🌐 اختر اللغة:","cit":"هل أنت من الرعايا الأجانب أم إيراني؟","iran":"🇮🇷 اختر خدمة الإيرانيين:","menu":"مرحباً 👋\nأهلاً بك في مساعد المهاجر.\nاختر الخدمة:","phone":"📱 أدخل رقم هاتف العميل.","partner_phone":"📱 أدخل رقم هاتف الشريك:","partner_pass":"🔐 أدخل كلمة مرور الشريك:","bad_login":"❌ رقم الهاتف أو كلمة المرور غير صحيحة.","no_partner":"❌ لم يتم العثور على الشريك.","balance":"💰 الرصيد: {amount:,} تومان","track":"🎫 أدخل رمز المتابعة.","not_found":"❌ لم يتم العثور على الرمز.","cancel":"تم إلغاء العملية والعودة إلى القائمة الرئيسية. ✅","bad":"يرجى اختيار أحد الخيارات المعروضة.","fida":"🪪 أرسل صورة وثيقة هوية العميل.","gov_fida":"🆔 أدخل رقم فيدا/الرقم الخاص بالعميل.","gov_yekta":"🔢 أدخل المعرف الفريد للعميل.","dob":"🎂 أدخل تاريخ الميلاد بالشكل 1356/01/01.","print":"🖨 اختر نوع الطباعة:","copies":"🔢 أدخل عدد النسخ لكل صفحة.","files":"📎 أرسل الملفات أو الصور. عند الانتهاء اختر تأكيد.","received":"✅ تم الاستلام. أرسل المزيد أو اختر تأكيد.","need_balance":"❌ الرصيد غير كافٍ. يرجى شحن الحساب أولاً.","payment":"🧾 تم إنشاء الطلب.\n🎫 رمز المتابعة: {code}\n💰 المبلغ: {amount:,} تومان","admin":"🛠 لوحة الإدارة الكاملة\nاختر خياراً:","bot_platform":"اختر تطبيق المراسلة:","bot_name":"🤖 أدخل اسم البوت:","bot_api":"🔑 أرسل رمز API:","bot_saved":"✅ تم حفظ البوت {name} لمنصة {platform}.","status":"📌 الحالة: {status}\n🎫 الرمز: {code}\n💰 المبلغ: {amount:,} تومان"}}

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
    """Rubika ChatKeypad clicks send text='custom text' and put the real button id in aux_data.button_id."""
    m=u.get("message") or u.get("new_message") or u
    if not isinstance(m,dict): return ""
    a=m.get("aux_data")
    if isinstance(a,str):
        try: a=json.loads(a)
        except Exception: a=None
    if isinstance(a,dict):
        bid=a.get("button_id")
        if bid is not None and str(bid).strip(): return str(bid).strip()
        bt=a.get("button_text")
        if bt is not None and str(bt).strip(): return str(bt).strip()
    for k in ("button_text","text"):
        if m.get(k): return str(m[k]).strip()
    return ""
def chat_of(u):
    if isinstance(u,dict) and u.get("chat_id"): return str(u.get("chat_id"))
    m=u.get("message") or u.get("new_message") or u
    return str((m or {}).get("chat_id") or (m or {}).get("chat_key") or "")
def user_of(u):
    m=u.get("message") or u.get("new_message") or u; s=(m or {}).get("sender") or {}
    return str((s or {}).get("user_id") or (m or {}).get("sender_id") or (m or {}).get("user_id") or chat_of(u))
def file_of(u):
    m=u.get("message") or u.get("new_message") or u; f=(m or {}).get("file") or {}
    return str(f.get("file_id") or (m or {}).get("file_id") or "")
def main_rows(uid):
    l=lang(uid)
    if l=="en": return [[("1","🪪 FIDA non-in-person"),("2","🖨 Printing")],[("3","🏛 Government access issue"),("4","🎫 Tracking")],[("5","📱 SIM services"),("6","📝 Screening & follow-up")],[("7","💰 My wallet"),("8","👥 Partner panel")],[("9","📞 Contact us"),("10","🔄 Start again")]]
    if l=="ar": return [[("1","🪪 خدمة فيدا"),("2","🖨 الطباعة")],[("3","🏛 مشكلة خدمات الحكومة"),("4","🎫 متابعة")],[("5","📱 خدمات الشريحة"),("6","📝 الفحص والمتابعة")],[("7","💰 محفظتي"),("8","👥 لوحة الشركاء")],[("9","📞 اتصل بنا"),("10","🔄 بدء من جديد")]]
    return [[("1","🪪 فیدای غیر حضوری"),("2","🖨 خدمات چاپ")],[("3","🏛 حل مشکل ورود اتباع دولت من"),("4","🎫 پیگیری")],[("5","📱 خدمات سیم کارت"),("6","📝 آزمون غربالگری و پیگیری")],[("7","💰 کیف پول من"),("8","🔵 👥 پنل همکاران")],[("9","📞 تماس با ما"),("10",RESTART)]]
def iran_rows(uid): return [[("1","🎫 پیگیری"),("2","🔵 👥 پنل همکاران")],[("10",RESTART)]]
def partner_rows(): return [[("1","➕ شارژ حساب"),("2","🔎 پیگیری کد")],[("3","📋 سوابق"),("4","💰 موجودی")],[("5","🏛 حل مشکل سامانه دولت من")],[("6","✉️ تیکت به مدیریت")],[("10",RESTART)]]
def admin_rows(): return [[("1","👥 کاربران"),("2","🤝 همکاران")],[("3","📋 درخواست‌ها"),("4","💰 شارژ و پرداخت‌ها")],[("5","🟢/🔴 خدمات ایرانی"),("6","🟢/🔴 خدمات اتباع")],[("7","📝 تغییر متن‌ها"),("8","💵 تغییر قیمت‌ها")],[("9","🤖 مدیریت بات‌ها"),("10","👤 مدیران")],[("11","📊 گزارش‌ها"),("12","🎫 تیکت‌ها")],[("13","📎 فایل‌های درخواست‌ها"),("14","🔄 همگام‌سازی")],[("15","🔄 شروع مجدد"),("0","⬅️ منوی اصلی")]]
def is_admin(uid): return str(uid) in ADMIN_IDS or STATE.get(str(uid),{}).get("admin") is True
def notify_admins(s):
    for a in ADMIN_IDS:
        try: send(a,s,admin_rows())
        except Exception: pass
def cancel(uid,chat):
    st=STATE.setdefault(str(uid),{"lang":"fa"}); partner=st.get("partner")
    st.clear(); st.update({"lang":st.get("lang","fa"),"step":"citizenship"})
    if partner: st["partner"]=partner
    send(chat,T(uid,"cit"),[[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')]])
def restart(uid,chat):
    STATE[str(uid)]={"lang":"fa","step":"language"}
    send(chat,TEXT["fa"]["lang"],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
def admin(uid,chat,x):
    uid=str(uid); st=STATE.setdefault(uid,{"lang":"fa","admin":True}); step=st.get("step")
    if step=="admin_price":
        a=x.split(maxsplit=1)
        if len(a)==2 and a[1].isdigit(): db.set_setting(a[0],a[1]); st["step"]="admin"; send(chat,"✅ قیمت ذخیره شد.",admin_rows()); return
        send(chat,"❌ قالب درست: کلید قیمت سپس مبلغ. مثال: price_government 500000",[[('0','⬅️ مدیریت')]]); return
    if step=="admin_text":
        key=st.get("text_key");
        if key: db.set_setting(key,x); st["step"]="admin"; send(chat,"✅ متن ذخیره شد.",admin_rows()); return
    if step=="admin_bot_platform":
        p={"1":"telegram","2":"rubika","3":"bale","4":"eitaa"}.get(x)
        if p: st["bot_platform"]=p; st["step"]="admin_bot_name"; send(chat,T(uid,"bot_name")); return
        send(chat,"❌ گزینه نامعتبر.",[[('1','Telegram'),('2','Rubika'),('3','Bale'),('4','Eitaa')]]); return
    if step=="admin_bot_name": st["bot_name"]=x; st["step"]="admin_bot_api"; send(chat,T(uid,"bot_api")); return
    if step=="admin_bot_api":
        p=st.get("bot_platform"); name=st.get("bot_name") or p; db.add_bot(p,name,x); st["step"]="admin"; send(chat,T(uid,"bot_saved",name=name,platform=p),admin_rows()); return
    if step=="admin":
        if x=="1":
            rs=db.conn.execute("SELECT platform,external_id,full_name,username FROM users ORDER BY id DESC LIMIT 50").fetchall(); send(chat,"👥 کاربران\n"+"\n".join(f"{r['platform']} | {r['full_name'] or '-'} | {r['external_id']}" for r in rs) if rs else "👥 کاربری ثبت نشده.",admin_rows()); return
        if x=="2":
            rs=db.conn.execute("SELECT name,phone,balance,active FROM partners ORDER BY id DESC").fetchall(); send(chat,"🤝 همکاران\n"+"\n".join(f"{r['name']} | {r['phone']} | {r['balance']:,} | {'فعال' if r['active'] else 'غیرفعال'}" for r in rs) if rs else "🤝 همکاری ثبت نشده.",admin_rows()); return
        if x=="3":
            rs=db.conn.execute("SELECT tracking_code,service_key,status,amount,platform FROM requests ORDER BY id DESC LIMIT 30").fetchall(); send(chat,"📋 درخواست‌ها\n"+"\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {r['amount']:,} | {r['platform']}" for r in rs) if rs else "📋 درخواستی نیست.",admin_rows()); return
        if x=="4":
            rs=db.conn.execute("SELECT id,partner_id,amount,status,created_at FROM topups ORDER BY id DESC LIMIT 30").fetchall(); send(chat,"💰 شارژها\n"+"\n".join(f"#{r['id']} | partner={r['partner_id']} | {r['amount']:,} | {r['status']}" for r in rs) if rs else "💰 شارژی ثبت نشده.",admin_rows()); return
        if x in {"5","6"}:
            group="ایرانی" if x=="5" else "اتباع"; services=db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall(); send(chat,f"🟢/🔴 باز و بسته خدمات {group}\n\n"+"\n".join(f"{r['key']} | {r['name']} | {r['price']:,} | {'باز' if r['active'] else 'بسته'}" for r in services)+"\n\nبرای تغییر: service_key open یا service_key close",admin_rows()); st["step"]="admin_service"; st["service_group"]=group; return
        if step=="admin_service":
            a=x.split();
            if len(a)==2 and a[1] in {"open","close","باز","بسته"}:
                active=1 if a[1] in {"open","باز"} else 0; db.conn.execute("UPDATE services SET active=? WHERE key=?",(active,a[0])); db.conn.commit(); st["step"]="admin"; send(chat,"✅ وضعیت خدمت تغییر کرد.",admin_rows()); return
        if x=="7":
            rs=db.conn.execute("SELECT key,value FROM settings WHERE key LIKE 'text_%' OR key LIKE 'welcome_%'").fetchall(); send(chat,"📝 تغییر متن‌ها\n\n"+"\n".join(f"{r['key']} = {r['value']}" for r in rs)+"\n\nکلید متن را بفرستید:",admin_rows()); st["step"]="admin_text_key"; return
        if step=="admin_text_key": st["text_key"]=x; st["step"]="admin_text"; send(chat,"✏️ متن جدید را ارسال کنید:"); return
        if x=="8": st["step"]="admin_price"; send(chat,"💵 کلید و قیمت را بفرستید. مثال: price_government 500000"); return
        if x=="9": st["step"]="admin_bot_platform"; send(chat,T(uid,"bot_platform"),[[('1','Telegram'),('2','Rubika'),('3','Bale'),('4','Eitaa')]]); return
        if x=="10": send(chat,"👤 مدیران\nمدیر اول و دوم از ADMIN_IDS و ADMIN_ID_2 خوانده می‌شوند. برای تغییر، متغیرهای Railway را تنظیم کنید.",admin_rows()); return
        if x=="11":
            users=db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]; partners=db.conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0]; reqs=db.conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]; send(chat,f"📊 گزارش‌ها\nکاربران: {users}\nهمکاران: {partners}\nدرخواست‌ها: {reqs}",admin_rows()); return
        if x=="12": send(chat,"🎫 تیکت‌ها\nتیکت‌های جدید از پنل همکار در همین کانال مدیریت نمایش داده می‌شوند.",admin_rows()); return
        if x=="13": send(chat,"📎 فایل‌های درخواست‌ها\nفایل‌ها در request_answers با شناسه فایل ذخیره می‌شوند و در اعلان درخواست ثبت می‌شوند.",admin_rows()); return
        if x=="14": send(chat,"🔄 همگام‌سازی\nوضعیت خدمات و تنظیمات از دیتابیس مشترک خوانده می‌شود؛ Telegram و Rubika از یک منبع استفاده می‌کنند.",admin_rows()); return
        if x=="15": restart(uid,chat); return
        if x=="0": cancel(uid,chat); return
    send(chat,T(uid,"admin"),admin_rows())
def handle(uid,chat,x,u):
    uid=str(uid); st=STATE.setdefault(uid,{"lang":"fa","step":"language"}); x=str(x).strip()
    if x.startswith("/start") or x==RESTART or x in {"شروع مجدد","🔄 Start again","🔄 بدء من جديد"}: restart(uid,chat); return
    if x==ADMIN_COMMAND: st["admin"]=True; st["step"]="admin"; send(chat,T(uid,"admin"),admin_rows()); return
    if x in {CANCEL,"انصراف","لغو","Cancel","cancel","إلغاء"}: cancel(uid,chat); return
    step=st.get("step")
    if st.get("admin") and step and step.startswith("admin"): admin(uid,chat,x); return
    if step=="language":
        z={"1":"fa","2":"en","3":"ar","🇮🇷 فارسی":"fa","🇬🇧 English":"en","🇸🇦 العربية":"ar","فارسی":"fa","English":"en","العربية":"ar"}.get(x)
        if not z: send(chat,TEXT["fa"]["lang"],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]]); return
        st["lang"]=z; st["step"]="citizenship"; cr=[[('1','🪪 اتباع هستم'),('2','🇮🇷 ایرانی هستم')] if z=='fa' else [('1','🪪 Foreign national'),('2','🇮🇷 Iranian')] if z=='en' else [('1','🪪 أجنبي'),('2','🇮🇷 إيراني')]]; send(chat,T(uid,"cit"),cr); return
    if step=="citizenship":
        if x in {"1","🪪 اتباع هستم","🪪 Foreign national","🪪 أجنبي"}: st["step"]="main"; send(chat,T(uid,"menu"),main_rows(uid)); return
        if x in {"2","🇮🇷 ایرانی هستم","🇮🇷 Iranian","🇮🇷 إيراني"}: st["step"]="iranian"; send(chat,T(uid,"iran"),iran_rows(uid)); return
    if step=="iranian":
        if x=="1": st["step"]="track"; send(chat,T(uid,"track"),[[('10',RESTART)]]); return
        if x=="2": st["step"]="partner_phone"; send(chat,T(uid,"partner_phone")); return
        if x=="10": restart(uid,chat); return
        send(chat,T(uid,"bad"),iran_rows(uid)); return
    if step in {"main","service"}:
        if x=="1": st["step"]="fida_phone"; send(chat,T(uid,"phone")); return
        if x=="2": st["step"]="print"; send(chat,T(uid,"print"),[[('1','⚫ سیاه و سفید'),('2','🌈 رنگی')]]); return
        if x=="3": st["step"]="gov_doc"; send(chat,"📄 نوع مدرک را انتخاب کنید:",[[('1','کارت آمایش'),('2','کارت موقت')],[('3','پاسپورت'),('4','دفترچه اقامت')]]); return
        if x=="4": st["step"]="track"; send(chat,T(uid,"track")); return
        if x=="5": st["step"]="sim"; send(chat,"📱 خدمات سیم کارت فعلاً بسته است.",main_rows(uid)); return
        if x=="6": st["step"]="screening"; send(chat,"📝 آزمون غربالگری فعلاً بسته است.",main_rows(uid)); return
        if x=="7": send(chat,T(uid,"balance",amount=db.setting(f"partner_balance_{uid}","0") or 0),main_rows(uid)); return
        if x=="8": st["step"]="partner_phone"; send(chat,T(uid,"partner_phone")); return
        if x=="9": send(chat,"📞 پشتیبانی: @Good_ok_2000",main_rows(uid)); return
        if x=="10": restart(uid,chat); return
        send(chat,T(uid,"bad"),main_rows(uid)); return
    if step=="partner_phone":
        p=normalize_phone(x)
        if not p: send(chat,"❌ شماره همراه را صحیح وارد کنید."); return
        st["partner_phone"]=p; st["step"]="partner_pass"; send(chat,T(uid,"partner_pass")); return
    if step=="partner_pass":
        phone=st.get("partner_phone"); p=db.get_partner(phone)
        if not p or not check_password(x,p["password_hash"]): st["step"]="partner_phone"; send(chat,T(uid,"bad_login")); return
        st["partner"]=phone; st["step"]="partner"; db.set_setting(f"partner_chat_{phone}",chat); send(chat,f"👥 پنل همکار\n📱 {phone}\n{T(uid,'balance',amount=p['balance'])}",partner_rows()); return
    if step=="partner":
        if x=="1": st["step"]="topup_amount"; send(chat,"💰 مبلغ شارژ را به تومان وارد کنید."); return
        if x=="2": st["step"]="track"; send(chat,T(uid,"track")); return
        if x=="3": send(chat,"📋 سوابق همکار فعلاً محدود به درخواست‌های اخیر است.",partner_rows()); return
        if x=="4":
            p=db.get_partner(st.get("partner")); send(chat,T(uid,"balance",amount=p['balance'] if p else 0),partner_rows()); return
        if x=="5": st["step"]="gov_doc"; send(chat,"📄 نوع مدرک را انتخاب کنید:",[[('1','کارت آمایش'),('2','کارت موقت')],[('3','پاسپورت'),('4','دفترچه اقامت')]]); return
        if x=="6": st["step"]="partner_ticket"; send(chat,"✉️ لطفاً متن تیکت خود را ارسال کنید:",[[('10',RESTART)]]); return
        if x=="10": restart(uid,chat); return
        send(chat,T(uid,"bad"),partner_rows()); return
    if step=="partner_ticket":
        if not x: send(chat,"✉️ متن تیکت را ارسال کنید."); return
        notify_admins(f"🎫 تیکت همکار\n👥 شماره همکار: {st.get('partner')}\n📝 متن:\n{x}"); st["step"]="partner"; send(chat,"✅ تیکت برای مدیریت ارسال شد.",partner_rows()); return
    if step=="topup_amount":
        if not x.isdigit(): send(chat,"❌ فقط عدد وارد کنید."); return
        st["topup_amount"]=int(x); st["step"]="topup_receipt"; send(chat,"🧾 تصویر رسید واریز را ارسال کنید."); return
    if step=="topup_receipt":
        f=file_of(u)
        if not f: send(chat,"📎 لطفاً تصویر رسید را ارسال کنید."); return
        amount=st.get("topup_amount",0); p=db.get_partner(st.get("partner"));
        if not p: send(chat,"❌ همکار پیدا نشد.",partner_rows()); return
        db.add_topup(p["id"],amount,f); st["step"]="partner"; notify_admins(f"💰 شارژ جدید\n👥 {p['phone']}\n💵 {amount:,} تومان\n🧾 رسید: {f}"); send(chat,"✅ رسید ثبت شد و برای تأیید مدیریت ارسال شد.",partner_rows()); return
    if step=="track":
        q=db.conn.execute("SELECT * FROM requests WHERE tracking_code=? ORDER BY id DESC LIMIT 1",(x,)).fetchone()
        if not q: send(chat,T(uid,"not_found"),[[('10',RESTART)]])
        else: send(chat,T(uid,"status",status=q['status'],code=q['tracking_code'],amount=q['amount']),partner_rows() if st.get('partner') else main_rows(uid))
        return
    if step=="fida_phone":
        p=normalize_phone(x)
        if not p: send(chat,"❌ شماره موبایل مشترک را صحیح وارد کنید."); return
        st["customer_phone"]=p; st["step"]="fida_file"; send(chat,T(uid,"fida")); return
    if step=="fida_file":
        f=file_of(u)
        if not f: send(chat,"📎 لطفاً تصویر مدرک را ارسال کنید."); return
        st["fida_file"]=f; st["step"]="main"; send(chat,"✅ مدارک دریافت شد. درخواست ثبت می‌شود.",main_rows(uid)); notify_admins(f"🔔 درخواست فیدا\n👤 کاربر: {uid}\n📱 شماره مشترک: {st.get('customer_phone')}\n📎 فایل: {f}"); return
    if step=="print":
        if x in {"1","⚫ سیاه و سفید"}: st["print_type"]="bw"; st["step"]="copies"; send(chat,T(uid,"copies")); return
        if x in {"2","🌈 رنگی"}: st["print_type"]="color"; st["step"]="copies"; send(chat,T(uid,"copies")); return
        send(chat,T(uid,"bad"),[[('1','⚫ سیاه و سفید'),('2','🌈 رنگی')]]); return
    if step=="copies":
        if not x.isdigit(): send(chat,"❌ تعداد نسخه را عددی وارد کنید."); return
        st["copies"]=int(x); st["step"]="print_files"; send(chat,T(uid,"files"),[[('1',OK),('10',RESTART)]]); return
    if step=="print_files":
        if x in {OK,"1"}:
            files=st.get("files",[]); amount=int(db.setting("price_print_bw", "0") or 0)*max(1,st.get("copies",1))*max(1,len(files)); notify_admins(f"🔔 درخواست چاپ\n👤 کاربر: {uid}\n💰 {amount:,} تومان\n📎 فایل‌ها: {len(files)}"); st["step"]="main"; send(chat,"✅ درخواست چاپ ثبت شد.",main_rows(uid)); return
        f=file_of(u)
        if f: st.setdefault("files",[]).append(f); notify_admins(f"📎 فایل چاپ از کاربر {uid}: {f}"); send(chat,T(uid,"received")); return
        send(chat,T(uid,"files"),[[('1',OK),('10',RESTART)]]); return
    if step=="gov_doc":
        docs={"1":"amaysh","2":"temporary","3":"passport","4":"residence"}
        if x not in docs: send(chat,"❌ نوع مدرک را انتخاب کنید."); return
        st["gov_doc"]=docs[x]; st["step"]="gov_files"; st["files"]=[]; send(chat,"📸 تصاویر مدرک را ارسال کنید. برای پاسپورت صفحه اول و تمدید؛ برای دفترچه اقامت تصاویر دفترچه و شماره دفترچه را ارسال کنید.",[[('1',OK),('10',RESTART)]]); return
    if step=="gov_files":
        if x in {OK,"1"}:
            files=st.get("files",[])
            if not files: send(chat,"❌ حداقل یک تصویر ارسال کنید."); return
            if st.get("gov_doc")=="residence": st["step"]="residence_number"; send(chat,"📗 شماره دفترچه اقامت را وارد کنید."); return
            notify_admins(f"🏛 درخواست دولت من\n👤 کاربر: {uid}\n📄 مدرک: {st.get('gov_doc')}\n📎 فایل‌ها: {len(files)}"); st["step"]="main"; send(chat,"✅ درخواست ثبت شد.",main_rows(uid)); return
        f=file_of(u)
        if f: st.setdefault("files",[]).append(f); send(chat,T(uid,"received")); return
        send(chat,"📸 تصویر مدرک را ارسال کنید یا تأیید را بزنید.",[[('1',OK),('10',RESTART)]]); return
    if step=="residence_number":
        if len(x)<3: send(chat,"❌ شماره دفترچه اقامت را صحیح وارد کنید."); return
        st["residence_number"]=x; notify_admins(f"📗 دفترچه اقامت\n👤 کاربر: {uid}\n🔢 شماره دفترچه: {x}\n📎 فایل‌ها: {len(st.get('files',[]))}"); st["step"]="main"; send(chat,"✅ اطلاعات دفترچه اقامت ثبت شد.",main_rows(uid)); return
    if step=="screening": send(chat,"📝 آزمون غربالگری فعلاً بسته است.",main_rows(uid)); st["step"]="main"; return
    send(chat,T(uid,"bad"),main_rows(uid))
def process(u):
    uid=user_of(u); chat=chat_of(u); x=text_of(u); handle(uid,chat,x,u)
