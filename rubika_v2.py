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
 "fa":{"lang":"🌐 زبان را انتخاب کنید:","cit":"آیا اتباع هستید یا ایرانی؟","iran":"🇮🇷 فعلاً خدماتی برای ایرانی فعال نیست.","menu":"سلام 👋\nبه «کمک یار مهاجر» خوش آمدید.\nخدمت موردنظر را انتخاب کنید:","phone":"📱 شماره موبایل مشترک را وارد کنید.","partner_phone":"📱 شماره همراه همکار را وارد کنید:","partner_pass":"🔐 رمز عبور همکار را وارد کنید:","bad_login":"❌ شماره همراه یا رمز عبور نادرست است.","no_partner":"❌ همکار پیدا نشد.","balance":"💰 موجودی اعتبار: {amount:,} تومان","track":"🎫 کد پیگیری را وارد کنید.","not_found":"❌ کد پیگیری پیدا نشد.","cancel":"عملیات لغو شد. به منوی اصلی برگشتید. ✅","bad":"لطفاً یکی از گزینه‌های نمایش‌داده‌شده را انتخاب کنید.","fida":"🪪 تصویر مدرک شناسایی مشترک را ارسال کنید.","gov_fida":"🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید.","gov_yekta":"🔢 شناسه یکتای مشترک را وارد کنید.","dob":"🎂 تاریخ تولد مشترک را به صورت 1356/01/01 وارد کنید.","print":"🖨 نوع چاپ را انتخاب کنید:","copies":"🔢 تعداد نسخه از هر صفحه را وارد کنید.","files":"📎 عکس‌ها یا فایل‌ها را یکی‌یکی ارسال کنید. در پایان «تأیید» را بزنید.","received":"✅ دریافت شد. مورد بعدی را بفرستید یا «تأیید» را بزنید.","need_balance":"❌ اعتبار کافی نیست. لطفاً ابتدا حساب را شارژ کنید.","payment":"🧾 درخواست ثبت شد.\n🎫 کد پیگیری: {code}\n💰 مبلغ: {amount:,} تومان","admin":"🛠 پنل مدیریت کامل\nگزینه موردنظر را انتخاب کنید:","bot_platform":"پیام‌رسان را انتخاب کنید:","bot_name":"🤖 نام بات را وارد کنید:","bot_api":"🔑 API را ارسال کنید:","bot_saved":"✅ بات {name} برای {platform} ثبت شد.","status":"📌 وضعیت: {status}\n🎫 کد: {code}\n💰 مبلغ: {amount:,} تومان"},
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
    old=STATE.get(str(uid),{}); p=old.get("partner_id"); STATE[str(uid)]={"lang":old.get("lang","fa"),"step":"menu",**({"partner_id":p} if p else {})}; send(chat,T(uid,"cancel"),main_rows(uid))
def request(uid,chat,key,amount):
    st=STATE[str(uid)]; pid=st.get("partner_id")
    if pid:
        p=db.conn.execute("SELECT balance FROM partners WHERE id=? AND active=1",(pid,)).fetchone()
        if not p or int(p["balance"])<amount: send(chat,T(uid,"need_balance"),partner_rows()); return
        db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",(amount,now(),pid)); db.conn.commit()
    user=db.user("rubika",uid,"",uid); rid,code=db.create_request(user,key,"rubika",amount); st["request_id"]=rid
    if pid:
        db.answer(rid,"partner_id",str(pid))
    db.audit("rubika",uid,"create_request",code,key)
    send(chat,T(uid,"payment",code=code,amount=amount),partner_rows() if pid else main_rows(uid)); notify_admins(f"🔔 درخواست جدید\n🎫 {code}\n🧩 {key}\n💰 {amount:,} تومان")
def admin(uid,chat,x):
    st=STATE[str(uid)]; step=st.get("step")
    if step=="admin_price":
        a=x.split()
        if len(a)==2 and a[1].isdigit(): db.set_setting(a[0],a[1]); st["step"]="admin"; send(chat,"✅ قیمت ذخیره شد.",admin_rows()); return
        send(chat,"❌ قالب: price_government 500000"); return
    if step=="bot_platform":
        p={"1":"eitaa","2":"bale","3":"telegram","4":"rubika","🤖 Eitaa":"eitaa","🤖 Bale":"bale","🤖 Telegram":"telegram","🤖 Rubika":"rubika"}.get(str(x).strip())
        if not p: send(chat,T(uid,"bot_platform"),[[("1","🤖 Eitaa"),("2","🤖 Bale")],[("3","🤖 Telegram"),("4","🤖 Rubika")],[("0",CANCEL)]]); return
        st["bot_platform"]=p; st["step"]="bot_name"; send(chat,T(uid,"bot_name"),[[("0",CANCEL)]]); return
    if step=="bot_name": st["bot_name"]=x; st["step"]="bot_api"; send(chat,T(uid,"bot_api"),[[("0",CANCEL)]]); return
    if step=="bot_api":
        db.add_bot(st["bot_platform"],st["bot_name"],"configured"); st["step"]="admin"; send(chat,T(uid,"bot_saved",name=st["bot_name"],platform=st["bot_platform"]),admin_rows()); return
    if x in {"0","⬅️ منوی اصلی"}: st["admin"]=False; st["step"]="menu"; send(chat,T(uid,"menu"),main_rows(uid)); return
    if x.startswith("1") or "همکاران" in x:
        rs=db.conn.execute("SELECT id,name,phone,balance,active FROM partners ORDER BY id DESC LIMIT 50").fetchall(); send(chat,"\n".join(f"#{r['id']} | {r['name']} | {r['phone']} | {int(r['balance']):,}" for r in rs) or "همکاری ثبت نشده.",admin_rows()); return
    if x.startswith("2") or "شارژ" in x:
        rs=db.conn.execute("SELECT t.id,p.name,t.amount,t.status FROM topups t JOIN partners p ON p.id=t.partner_id ORDER BY t.id DESC LIMIT 30").fetchall(); send(chat,"\n".join(f"#{r['id']} | {r['name']} | {int(r['amount']):,} | {r['status']}" for r in rs) or "شارژی نیست.",admin_rows()); return
    if x.startswith("3") or "درخواست" in x:
        rs=db.conn.execute("SELECT tracking_code,service_key,status,amount,payment_status FROM requests ORDER BY id DESC LIMIT 50").fetchall(); send(chat,"\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,} | {r['payment_status']}" for r in rs) or "درخواستی نیست.",admin_rows()); return
    if x.startswith("4") or "پرداخت" in x:
        rs=db.conn.execute("SELECT tracking_code,service_key,amount,payment_status FROM requests WHERE payment_status!='paid' ORDER BY id DESC LIMIT 30").fetchall(); send(chat,"\n".join(f"{r['tracking_code']} | {r['service_key']} | {int(r['amount']):,} | {r['payment_status']}" for r in rs) or "پرداخت معلقی نیست.",admin_rows()); return
    if x.startswith("5") or "قیمت" in x: st["step"]="admin_price"; send(chat,"⚙️ قیمت را بفرستید؛ مثال: price_government 500000",admin_rows()); return
    if x.startswith("6") or "افزودن بات" in x: st["step"]="bot_platform"; send(chat,T(uid,"bot_platform"),[[('1','🤖 Eitaa'),('2','🤖 Bale')],[('3','🤖 Telegram'),('4','🤖 Rubika')],[('0',CANCEL)]]); return
    if x.startswith("7") or "متصل" in x:
        rs=db.bots(); send(chat,"\n".join(f"#{r['id']} | {r['platform']} | {r['bot_name']} | {r['status']}" for r in rs) or "باتی ثبت نشده.",admin_rows()); return
    if x.startswith("8") or "گزارش" in x:
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
        if x=="1" or any(q in x for q in ("اتباع","Foreign","أجنبي")): st["step"]="menu"; send(chat,T(uid,"menu"),main_rows(uid)); return
        if x=="2" or any(q in x for q in ("ایرانی","Iranian","إيراني")): st["step"]="iranian"; send(chat,T(uid,"iran"),[[('1','👥 پنل همکاران'),('2','🎫 پیگیری')]]); return
        send(chat,T(uid,"bad")); return
    if step=="iranian":
        if x.startswith("1") or "همکار" in x: st["step"]="partner_phone"; send(chat,T(uid,"partner_phone"),[[('0',CANCEL)]]); return
        if x.startswith("2") or "پیگیری" in x: st["step"]="track"; send(chat,T(uid,"track"),[[('0',CANCEL)]]); return
    if step=="menu":
        if x.startswith("1"): st["step"]="fida_doc"; send(chat,T(uid,"fida"),[[('0',CANCEL)]]); return
        if x.startswith("2"): st["step"]="print_color"; send(chat,T(uid,"print"),[[('1','⚫ سیاه و سفید'),('2','🌈 رنگی')],[('0',CANCEL)]]); return
        if x.startswith("3"): st["step"]="gov_fida"; send(chat,T(uid,"gov_fida"),[[('0',CANCEL)]]); return
        if x.startswith("4"): st["step"]="track"; send(chat,T(uid,"track"),[[('0',CANCEL)]]); return
        if x.startswith("7"): p=db.conn.execute("SELECT balance FROM partners WHERE id=?",(st.get("partner_id"),)).fetchone() if st.get("partner_id") else None; send(chat,T(uid,"balance",amount=int(p['balance']) if p else 0),main_rows(uid)); return
        if x.startswith("8"): st["step"]="partner_phone"; send(chat,T(uid,"partner_phone"),[[('0',CANCEL)]]); return
        send(chat,T(uid,"menu"),main_rows(uid)); return
    if step=="partner_phone":
        p=db.partner(x)
        if not p: send(chat,T(uid,"no_partner")); return
        st["phone"]=x; st["step"]="partner_pass"; send(chat,T(uid,"partner_pass"),[[('0',CANCEL)]]); return
    if step=="partner_pass":
        p=db.partner(st.get("phone",""))
        if not p or not check_password(x,p["password_hash"]): send(chat,T(uid,"bad_login")); return
        st["partner_id"]=p["id"]; st["step"]="partner"; send(chat,T(uid,"balance",amount=int(p["balance"])),partner_rows()); return
    if step=="partner":
        if x.startswith("5") or "دولت من" in x:
            st["step"]="partner_gov_fida"
            send(chat,"🏛 حل مشکل سامانه دولت من\\n\\n🆔 شناسه فیدا/اختصاصی مشترک را وارد کنید:",[[("0",CANCEL)]])
            return
    if step=="partner":
        if x.startswith("1"): st["step"]="topup_amount"; send(chat,"💰 مبلغ شارژ را به تومان وارد کنید:",[[('0',CANCEL)]]); return
        if x.startswith("2"): st["step"]="track_partner"; send(chat,T(uid,"track"),[[('0',CANCEL)]]); return
        if x.startswith("3"):
            rs=db.conn.execute("SELECT tracking_code,service_key,status,amount FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20",(st["partner_id"],)).fetchall(); send(chat,"\n".join(f"{r['tracking_code']} | {r['service_key']} | {r['status']} | {int(r['amount']):,}" for r in rs) or "سابقه‌ای نیست.",partner_rows()); return
        if x.startswith("4"): p=db.conn.execute("SELECT balance FROM partners WHERE id=?",(st["partner_id"],)).fetchone(); send(chat,T(uid,"balance",amount=int(p['balance']) if p else 0),partner_rows()); return
    if step in {"track","track_partner"}:
        r=db.conn.execute("SELECT * FROM requests WHERE tracking_code=?",(x,)).fetchone();
        if not r: send(chat,T(uid,"not_found"),partner_rows() if st.get("partner_id") else main_rows(uid)); return
        send(chat,T(uid,"status",status=r['status'],code=r['tracking_code'],amount=int(r['amount'])),partner_rows() if st.get("partner_id") else main_rows(uid)); return
    if step=="topup_amount":
        try: a=int(x.replace(',','').replace('٬',''))
        except: send(chat,"❌ مبلغ را فقط عددی وارد کنید."); return
        if a<=0: send(chat,"❌ مبلغ نامعتبر است."); return
        st["topup_amount"]=a; st["step"]="topup_receipt"; send(chat,f"💳 {a:,} تومان\n💳 شماره کارت: {db.setting('card_number')}\n👤 به نام: {db.setting('card_owner')}\n📸 رسید را ارسال کنید.",[[('0',CANCEL)]]); return
    if step=="print_color": st["print_color"]="bw" if x.startswith('1') else 'color'; st["step"]="print_copies"; send(chat,T(uid,"copies"),[[('0',CANCEL)]]); return
    if step=="print_copies":
        if not x.isdigit() or int(x)<=0: send(chat,"❌ تعداد نسخه نامعتبر است."); return
        st["copies"]=int(x); st["step"]="print_files"; st["files"]=[]; send(chat,T(uid,"files"),[[('1',OK),('0',CANCEL)]]); return
    if step=="print_files" and x in {OK,"1","تأیید","Confirm"}:
        amount=int(db.setting("price_print_bw" if st.get("print_color")=="bw" else "price_print_color","0") or 0)*int(st.get("copies",1)); request(uid,chat,"print",amount); return
    if step=="fida_phone": st["customer_phone"]=x; request(uid,chat,"fida",int(db.setting("price_fida","0") or 0)); return
    if step in {"gov_fida","partner_gov_fida"}:
        if not x or x=="__MEDIA__":
            send(chat,"❌ شناسه فیدا/اختصاصی را به‌صورت متنی وارد کنید.",[[("0",CANCEL)]])
            return
        st["gov_fida"]=x; st["step"]="gov_yekta"
        send(chat,"🔢 شناسه یکتای مشترک را وارد کنید:",[[("0",CANCEL)]])
        return
    if step=="gov_yekta":
        if not x or x=="__MEDIA__":
            send(chat,"❌ شناسه یکتا را به‌صورت متنی وارد کنید.",[[("0",CANCEL)]])
            return
        st["gov_yekta"]=x; st["step"]="gov_dob"
        send(chat,T(uid,"dob"),[[("0",CANCEL)]])
        return
    if step=="gov_dob":
        if not re.fullmatch(r"\d{4}/\d{2}/\d{2}",x): send(chat,T(uid,"dob")); return
        request(uid,chat,"government",int(db.setting("price_government","500000") or 500000)); return
    if step in {"fida_doc","topup_receipt","print_files"}:
        fid=file_of(u)
        if not fid: send(chat,"📎 فایل یا عکس را ارسال کنید."); return
        if step=="fida_doc": st["fida_doc"]=fid; st["step"]="fida_phone"; send(chat,T(uid,"phone"),[[('0',CANCEL)]]); return
        if step=="topup_receipt": tid=db.add_topup(st["partner_id"],st["topup_amount"],fid); st["step"]="partner"; notify_admins(f"🔔 رسید شارژ جدید #{tid}\n💰 {st['topup_amount']:,} تومان"); send(chat,f"✅ رسید شارژ #{tid} ثبت شد و منتظر تأیید مدیر است.",partner_rows()); return
        st.setdefault("files",[]).append(fid); send(chat,T(uid,"received"),[[('1',OK),('0',CANCEL)]]); return
def process(u):
    c=chat_of(u); uid=user_of(u)
    if not c or not uid: return
    db.user("rubika",uid,"",uid); x=text_of(u); handle(uid,c,x,u) if x else handle(uid,c,"__MEDIA__",u)
def main():
    global OFFSET
    me=call("getMe"); log.info("Rubika getMe OK: %s",me); log.info("Rubika v2 polling started")
    while True:
        try:
            p={"limit":50};
            if OFFSET: p["offset_id"]=OFFSET
            d=call("getUpdates",p); updates=d.get("updates",[]) if isinstance(d,dict) else d
            if isinstance(d,dict) and d.get("next_offset_id"): OFFSET=d["next_offset_id"]
            for u in updates or []:
                try: process(u)
                except Exception: log.exception("Rubika update failed")
        except Exception: log.exception("Rubika polling error")
        time.sleep(.5)
if __name__=="__main__": main()
