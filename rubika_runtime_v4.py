import importlib.abc, importlib.util, sys, json

def install(m):
    if getattr(m, '_netyar_v4_installed', False): return
    old_text = m.text_of
    def text_of(u):
        msg = u.get('message') or u.get('new_message') or u
        if isinstance(msg, dict):
            aux = msg.get('aux_data')
            if isinstance(aux, dict) and aux.get('button_id') is not None:
                return str(aux['button_id']).strip()
            if isinstance(aux, str):
                try:
                    a=json.loads(aux)
                    if isinstance(a,dict) and a.get('button_id') is not None: return str(a['button_id']).strip()
                except Exception: pass
        return old_text(u)
    m.text_of=text_of
    old_main=m.main_rows
    def main_rows(uid):
        out=[]
        for row in old_main(uid):
            row=[i for i in row if not (isinstance(i,(tuple,list)) and len(i)>=2 and str(i[0])=='0')]
            if row: out.append(row)
        out.append([('99','🔄 شروع مجدد')]); return out
    m.main_rows=main_rows
    old_partner=m.partner_rows
    def partner_rows():
        out=[]
        for row in old_partner():
            row=[i for i in row if not (isinstance(i,(tuple,list)) and len(i)>=2 and str(i[0])=='0')]
            if row: out.append(row)
        out.append([('6','🎫 ارسال تیکت به مدیریت')]); out.append([('99','🔄 شروع مجدد')]); return out
    m.partner_rows=partner_rows
    def admin_rows():
        return [[('1','👥 مدیریت همکاران'),('2','💰 مدیریت شارژها')],[('3','📋 مدیریت درخواست‌ها'),('4','💳 مدیریت پرداخت‌ها')],[('5','🛠 مدیریت خدمات'),('6','📝 مدیریت متن‌ها')],[('7','💵 مدیریت قیمت‌ها'),('8','🤖 مدیریت بات‌ها')],[('9','📊 گزارش‌ها'),('10','👤 مدیریت مدیران')],[('11','🎫 مدیریت تیکت‌ها'),('12','⚙️ تنظیمات')],[('99','🔄 شروع مجدد')]]
    m.admin_rows=admin_rows
    old_admin=m.admin
    def admin(uid,chat,x):
        st=m.STATE.setdefault(str(uid),{}); step=st.get('step'); x=str(x).strip()
        if step=='admin':
            if x=='1':
                rs=m.db.conn.execute('SELECT phone,name,balance,active FROM partners ORDER BY phone').fetchall(); text='👥 مدیریت همکاران\n'+('\n'.join('{} | {} | {:,} | {}'.format(r['phone'],r['name'],int(r['balance'] or 0),'فعال' if r['active'] else 'غیرفعال') for r in rs) if rs else 'همکاری ثبت نشده است.'); return m.send(chat,text,m.admin_rows())
            if x=='2':
                rs=m.db.conn.execute('SELECT id,partner_id,amount,status FROM topups ORDER BY id DESC LIMIT 20').fetchall(); text='💰 مدیریت شارژها\n'+('\n'.join('#{} | همکار {} | {:,} | {}'.format(r['id'],r['partner_id'],int(r['amount'] or 0),r['status']) for r in rs) if rs else 'شارژی ثبت نشده است.'); return m.send(chat,text,m.admin_rows())
            if x=='3':
                rs=m.db.conn.execute('SELECT tracking_code,service_key,platform,status,amount FROM requests ORDER BY id DESC LIMIT 20').fetchall(); text='📋 مدیریت درخواست‌ها\n'+('\n'.join('{} | {} | {} | {} | {:,}'.format(r['tracking_code'],r['service_key'],r['platform'],r['status'],int(r['amount'] or 0)) for r in rs) if rs else 'درخواستی ثبت نشده است.'); return m.send(chat,text,m.admin_rows())
            if x=='4':
                rs=m.db.conn.execute('SELECT tracking_code,payment_status,payment_method,amount FROM requests ORDER BY id DESC LIMIT 20').fetchall(); text='💳 مدیریت پرداخت‌ها\n'+('\n'.join('{} | {} | {} | {:,}'.format(r['tracking_code'],r['payment_status'],r['payment_method'] or '-',int(r['amount'] or 0)) for r in rs) if rs else 'پرداختی ثبت نشده است.'); return m.send(chat,text,m.admin_rows())
            if x=='5': st['step']='admin_services'; return m.send(chat,'🛠 مدیریت باز و بسته خدمات\nگروه خدمات را انتخاب کنید:',[[('foreign','🇦🇫 خدمات اتباع'),('iranian','🇮🇷 خدمات ایرانی')],[('99','🔄 شروع مجدد')]])
            if x=='6': st['step']='admin_text'; return m.send(chat,'📝 مدیریت متن‌ها\nکلید متن را بفرستید؛ سپس متن جدید را ارسال کنید.\nمثال: welcome_fa',[[('99','🔄 شروع مجدد')]])
            if x=='7': st['step']='admin_price'; return m.send(chat,'💵 مدیریت قیمت‌ها\nمثال: price_government 500000',[[('99','🔄 شروع مجدد')]])
            if x=='8': st['step']='admin_bot_platform'; return m.send(chat,'🤖 مدیریت بات‌ها\nپیام‌رسان را انتخاب کنید:',[[('1','Telegram'),('2','Rubika')],[('3','Bale'),('4','Eitaa')],[('99','🔄 شروع مجدد')]])
            if x=='9':
                total=m.db.conn.execute('SELECT COUNT(*) c FROM requests').fetchone()['c']; partners=m.db.conn.execute('SELECT COUNT(*) c FROM partners').fetchone()['c']; active=m.db.conn.execute('SELECT COUNT(*) c FROM services WHERE active=1').fetchone()['c']; return m.send(chat,'📊 گزارش‌ها\nدرخواست‌ها: {}\nهمکاران: {}\nخدمات باز: {}'.format(total,partners,active),m.admin_rows())
            if x=='10': return m.send(chat,'👤 مدیریت مدیران\nمدیر اول و دوم از ADMIN_IDS و ADMIN_ID_2 کنترل می‌شوند.',m.admin_rows())
            if x=='11': return m.send(chat,'🎫 مدیریت تیکت‌ها\nتیکت همکار ابتدا متن را می‌گیرد و برای مدیریت ارسال می‌کند.',m.admin_rows())
            if x=='12': return m.send(chat,'⚙️ تنظیمات\nوضعیت خدمات، متن‌ها، قیمت‌ها و بات‌ها از همین پنل قابل مدیریت هستند.',m.admin_rows())
        if step=='admin_services':
            if x in {'foreign','🇦🇫 خدمات اتباع','1'}:
                st['service_group']='foreign'; rs=m.db.conn.execute('SELECT key,name,price,active FROM services ORDER BY id').fetchall(); buttons=[[(f'svc:{r["key"]}',('🟢 ' if r['active'] else '🔴 ')+str(r['name']))] for r in rs]; return m.send(chat,'🇦🇫 خدمات اتباع\nبرای باز/بسته کردن هر خدمت روی آن بزنید.',buttons+[[('back_admin','⬅️ مدیریت')],[('99','🔄 شروع مجدد')]])
            if x in {'iranian','🇮🇷 خدمات ایرانی','2'}:
                st['service_group']='iranian'; rs=m.db.conn.execute('SELECT key,name,price,active FROM services ORDER BY id').fetchall(); buttons=[[(f'svc:{r["key"]}',('🟢 ' if r['active'] else '🔴 ')+str(r['name']))] for r in rs]; return m.send(chat,'🇮🇷 خدمات ایرانی\nبرای باز/بسته کردن هر خدمت روی آن بزنید.',buttons+[[('back_admin','⬅️ مدیریت')],[('99','🔄 شروع مجدد')]])
            if x=='back_admin': st['step']='admin'; return m.send(chat,m.T(uid,'admin'),m.admin_rows())
            if x.startswith('svc:'):
                key=x[4:]; r=m.db.conn.execute('SELECT name,active,price FROM services WHERE key=?',(key,)).fetchone()
                if not r:return m.send(chat,'❌ خدمت پیدا نشد.',m.admin_rows())
                new=0 if int(r['active'] or 0) else 1; m.db.conn.execute('UPDATE services SET active=? WHERE key=?',(new,key)); m.db.conn.commit(); return m.send(chat,('{}: {}\n💰 {:,} تومان'.format('🟢 خدمت باز شد' if new else '🔴 خدمت بسته شد',r['name'],int(r['price'] or 0))),m.admin_rows())
            return m.send(chat,'❌ گزینه نامعتبر است.',[[('foreign','🇦🇫 خدمات اتباع'),('iranian','🇮🇷 خدمات ایرانی')],[('99','🔄 شروع مجدد')]])
        if step=='admin_text': st['text_key']=x; st['step']='admin_text_value'; return m.send(chat,'📝 متن جدید برای «{}» را ارسال کنید.'.format(x),[[('99','🔄 شروع مجدد')]])
        if step=='admin_text_value': m.db.set_setting(st.get('text_key',''),x); st['step']='admin'; return m.send(chat,'✅ متن ذخیره شد.',m.admin_rows())
        if step=='admin_price':
            parts=x.split(maxsplit=1)
            if len(parts)==2 and parts[1].isdigit(): m.db.set_setting(parts[0],parts[1]); st['step']='admin'; return m.send(chat,'✅ قیمت ذخیره شد.',m.admin_rows())
            return m.send(chat,'❌ قالب درست: price_government 500000',[[('99','🔄 شروع مجدد')]])
        if step=='admin_bot_platform':
            p={'1':'telegram','2':'rubika','3':'bale','4':'eitaa'}.get(x)
            if not p:return m.send(chat,'❌ پیام‌رسان را انتخاب کنید.',[[('1','Telegram'),('2','Rubika')],[('3','Bale'),('4','Eitaa')],[('99','🔄 شروع مجدد')]])
            st['bot_platform']=p; st['step']='admin_bot_name'; return m.send(chat,'🤖 نام بات را وارد کنید:',[[('99','🔄 شروع مجدد')]])
        if step=='admin_bot_name': st['bot_name']=x; st['step']='admin_bot_api'; return m.send(chat,'🔑 API بات را ارسال کنید:',[[('99','🔄 شروع مجدد')]])
        if step=='admin_bot_api':
            p=st.get('bot_platform','unknown'); m.db.add_bot(p,st.get('bot_name','Bot'),x); st['step']='admin'; return m.send(chat,'✅ اطلاعات بات ذخیره شد.',m.admin_rows())
        return old_admin(uid,chat,x)
    m.admin=admin
    old_handle=m.handle
    def handle(uid,chat,x,u):
        x=str(x).strip(); step=m.STATE.get(str(uid),{}).get('step')
        if x in {'99','🔄 شروع مجدد'}:
            st=m.STATE.setdefault(str(uid),{}); st.clear(); st.update({'lang':'fa','step':'language'}); return m.send(chat,m.TEXT['fa']['lang'],[[('1','🇮🇷 فارسی'),('2','🇬🇧 English'),('3','🇸🇦 العربية')]])
        if step=='citizenship' and x in {'2','🇮🇷 ایرانی هستم','🇮🇷 Iranian','🇮🇷 إيراني'}:
            m.STATE[str(uid)]['step']='iranian'; return m.send(chat,'🇮🇷 منوی خدمات ایرانی:',[[('1','👥 پنل همکاران')],[('2','🎫 پیگیری')],[('99','🔄 شروع مجدد')]])
        if step=='iranian':
            if x in {'1','👥 پنل همکاران'}: m.STATE[str(uid)]['step']='partner_phone'; return m.send(chat,m.T(uid,'partner_phone'),[[('0',m.CANCEL)]])
            if x in {'2','🎫 پیگیری'}: m.STATE[str(uid)]['step']='track'; return m.send(chat,m.T(uid,'track'),[[('0',m.CANCEL)]])
        if step=='partner' and x in {'6','🎫 ارسال تیکت به مدیریت'}:
            m.STATE[str(uid)]['step']='partner_ticket'; return m.send(chat,'🎫 لطفاً متن تیکت خود را ارسال کنید.\nمشکل یا درخواست خود را کامل بنویسید.',[[('0',m.CANCEL)]])
        if step=='partner_ticket':
            if x in {'0',m.CANCEL,'❌ انصراف'}: return old_handle(uid,chat,m.CANCEL,u)
            try: m.notify_admins('🎫 تیکت همکار\n👥 {}\n🆔 {}\n\n{}'.format(m.STATE[str(uid)].get('partner','-'),uid,x))
            except Exception: pass
            m.STATE[str(uid)]['step']='partner'; return m.send(chat,'✅ تیکت برای مدیریت ارسال شد.',m.partner_rows())
        return old_handle(uid,chat,x,u)
    m.handle=handle; m._netyar_v4_installed=True

class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname!='rubika_v2': return None
        try: sys.meta_path.remove(self)
        except ValueError: pass
        spec=importlib.util.find_spec(fullname)
        if spec is None: return None
        old=spec.loader
        class Loader(importlib.abc.Loader):
            def create_module(self,s): return old.create_module(s) if hasattr(old,'create_module') else None
            def exec_module(self,m): old.exec_module(m); install(m)
        spec.loader=Loader(); return spec
sys.meta_path.insert(0,Finder())
if 'rubika_v2' in sys.modules:
    install(sys.modules['rubika_v2'])
