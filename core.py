import os, sqlite3, secrets, hashlib, hmac, shutil, pathlib
from datetime import datetime, timezone
_mount=os.getenv("RAILWAY_VOLUME_MOUNT_PATH","").strip()
_default_db=os.path.join(_mount,"netyar.db") if _mount else "netyar.db"
DB_PATH=os.getenv("DB_PATH","").strip() or _default_db
CARD_NUMBER=os.getenv("PAYMENT_CARD","").strip()
CARD_OWNER=os.getenv("PAYMENT_CARD_OWNER","").strip()
def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
def hash_password(p):
    salt=secrets.token_hex(16); digest=hashlib.pbkdf2_hmac("sha256",p.encode(),salt.encode(),120000).hex(); return salt+"$"+digest
def check_password(p,stored):
    try:
        if "$" in str(p) and "$" not in str(stored): p,stored=stored,p
        salt,digest=str(stored).split("$",1); got=hashlib.pbkdf2_hmac("sha256",str(p).encode(),salt.encode(),120000).hex(); return hmac.compare_digest(got,digest)
    except Exception:return False
class Database:
    def __init__(self,path=DB_PATH):
        pathlib.Path(path).parent.mkdir(parents=True,exist_ok=True)
        if os.getenv("RAILWAY_VOLUME_MOUNT_PATH") and not os.path.exists(path) and os.path.exists("netyar.db"):
            try: shutil.copy2("netyar.db",path)
            except Exception: pass
        self.conn=sqlite3.connect(path,check_same_thread=False,timeout=30); self.conn.row_factory=sqlite3.Row; self.conn.execute("PRAGMA journal_mode=WAL"); self.conn.execute("PRAGMA busy_timeout=30000"); self.init()
    def init(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, external_id TEXT, username TEXT DEFAULT '', full_name TEXT DEFAULT '', phone TEXT DEFAULT '', id_code TEXT DEFAULT '', created_at TEXT, updated_at TEXT, UNIQUE(platform,external_id));
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, name TEXT, description TEXT DEFAULT '', price INTEGER DEFAULT 0, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, tracking_code TEXT UNIQUE, user_id INTEGER, service_key TEXT, platform TEXT, status TEXT DEFAULT 'new', amount INTEGER DEFAULT 0, payment_status TEXT DEFAULT 'unpaid', payment_method TEXT DEFAULT '', payment_note TEXT DEFAULT '', created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS request_answers(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, field_key TEXT, answer TEXT DEFAULT '', file_id TEXT DEFAULT '', created_at TEXT);
        CREATE TABLE IF NOT EXISTS partners(id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE, password_hash TEXT, name TEXT DEFAULT '', active INTEGER DEFAULT 1, balance INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS topups(id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id INTEGER, amount INTEGER, receipt_file_id TEXT DEFAULT '', status TEXT DEFAULT 'pending', created_at TEXT, reviewed_at TEXT, note TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS admins(platform TEXT, external_id TEXT, role TEXT DEFAULT 'owner', active INTEGER DEFAULT 1, PRIMARY KEY(platform,external_id));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, actor_id TEXT, action TEXT, target TEXT DEFAULT '', details TEXT DEFAULT '', created_at TEXT);
        CREATE TABLE IF NOT EXISTS bot_integrations(id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT UNIQUE, bot_name TEXT DEFAULT '', token_ref TEXT DEFAULT '', active INTEGER DEFAULT 0, status TEXT DEFAULT 'configured', created_at TEXT, updated_at TEXT);
        """)
        defaults={"welcome_fa":"سلام و خوش آمدید 🌷\nبه بات «کمک یار مهاجر» خوش آمدید.","welcome_en":"Welcome to Mohajer Helper.","welcome_ar":"مرحباً بكم في مساعد المهاجر.","card_number":CARD_NUMBER,"card_owner":CARD_OWNER,"price_fida":"0","price_print_bw":"0","price_print_color":"0","price_government":"500000","bot_open":"1"}
        for k,v in defaults.items(): self.conn.execute("INSERT OR IGNORE INTO settings VALUES(?,?)",(k,v))
        sv=[("fida","فیدای غیر حضوری","ارسال مدرک شناسایی و شماره همراه",0),("print","خدمات چاپ","چاپ فایل و عکس",0),("government","حل مشکل ورود اتباع سامانه دولت من","ثبت درخواست و بررسی مدارک",500000)]
        for k,n,d,p in sv:self.conn.execute("INSERT OR IGNORE INTO services(key,name,description,price) VALUES(?,?,?,?)",(k,n,d,p))
        # Never ship a default partner password in source control. Provision a
        # partner only when explicit credentials are supplied through Railway.
        phone=os.getenv("INITIAL_PARTNER_PHONE","").strip(); password=os.getenv("INITIAL_PARTNER_PASSWORD","").strip(); name=os.getenv("INITIAL_PARTNER_NAME","همکار").strip()
        if phone and password and not self.conn.execute("SELECT 1 FROM partners WHERE phone=?",(phone,)).fetchone():
            self.conn.execute("INSERT INTO partners(phone,password_hash,name,created_at,updated_at) VALUES(?,?,?,?,?)",(phone,hash_password(password),name,now(),now()))
        self.conn.commit()
    def setting(self,k,default=""):
        r=self.conn.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone(); return r["value"] if r else default
    def set_setting(self,k,v): self.conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(k,str(v))); self.conn.commit()
    def user(self,platform,external_id,username="",full_name=""):
        t=now(); self.conn.execute("""INSERT INTO users(platform,external_id,username,full_name,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(platform,external_id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name,updated_at=excluded.updated_at""",(platform,str(external_id),username or "",full_name or "",t,t)); self.conn.commit(); return self.conn.execute("SELECT id FROM users WHERE platform=? AND external_id=?",(platform,str(external_id))).fetchone()["id"]
    def service(self,key): return self.conn.execute("SELECT * FROM services WHERE key=? AND active=1",(key,)).fetchone()
    def create_request(self,user_id,service_key,platform,amount):
        code="NYM-"+secrets.token_hex(4).upper(); t=now(); cur=self.conn.execute("INSERT INTO requests(tracking_code,user_id,service_key,platform,status,amount,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(code,user_id,service_key,platform,"awaiting_payment",amount,t,t)); self.conn.commit(); return cur.lastrowid,code
    def answer(self,rid,key,answer="",file_id=""): self.conn.execute("INSERT INTO request_answers(request_id,field_key,answer,file_id,created_at) VALUES(?,?,?,?,?)",(rid,key,answer or "",file_id or "",now()))
    def partner(self,phone): return self.conn.execute("SELECT * FROM partners WHERE phone=? AND active=1",(str(phone).strip(),)).fetchone()
    def get_partner(self,phone): return self.partner(phone)
    def add_partner(self,phone,password,name): self.conn.execute("INSERT INTO partners(phone,password_hash,name,created_at,updated_at) VALUES(?,?,?,?,?)",(phone.strip(),hash_password(password),name.strip(),now(),now())); self.conn.commit()
    def add_topup(self,pid,amount,file_id):
        cur=self.conn.execute("INSERT INTO topups(partner_id,amount,receipt_file_id,status,created_at) VALUES(?,?,?,?,?)",(pid,amount,file_id,"pending",now())); self.conn.commit(); return cur.lastrowid
    def audit(self,*a): self.conn.execute("INSERT INTO audit_log(platform,actor_id,action,target,details,created_at) VALUES(?,?,?,?,?,?)",(*map(str,a[:5]),now())); self.conn.commit()
    def add_bot(self,platform,bot_name,token_ref): self.conn.execute("INSERT OR REPLACE INTO bot_integrations(platform,bot_name,token_ref,active,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(platform,bot_name,token_ref,0,"configured",now(),now())); self.conn.commit()
    def bots(self): return self.conn.execute("SELECT id,platform,bot_name,active,status,created_at,updated_at FROM bot_integrations ORDER BY id DESC").fetchall()
db=Database()
