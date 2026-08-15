import os
import sqlite3
import secrets
import logging
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "netyar.db")
log = logging.getLogger("netyar")

def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.init()

    def init(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, platform TEXT NOT NULL DEFAULT 'telegram',
          username TEXT DEFAULT '', full_name TEXT DEFAULT '', phone TEXT DEFAULT '',
          id_code TEXT DEFAULT '', city TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS services(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT '',
          price INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
          payment_methods TEXT NOT NULL DEFAULT 'code,card', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS service_steps(
          id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, step_no INTEGER NOT NULL,
          prompt TEXT NOT NULL, input_type TEXT NOT NULL DEFAULT 'text', required INTEGER NOT NULL DEFAULT 1,
          file_types TEXT DEFAULT '', max_file_mb INTEGER NOT NULL DEFAULT 10,
          price_delta INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, service_id INTEGER NOT NULL,
          platform TEXT NOT NULL DEFAULT 'telegram', status TEXT NOT NULL DEFAULT 'new',
          payment_method TEXT DEFAULT '', amount INTEGER NOT NULL DEFAULT 0,
          payment_status TEXT NOT NULL DEFAULT 'unpaid', payment_note TEXT DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(service_id) REFERENCES services(id)
        );
        CREATE TABLE IF NOT EXISTS request_answers(
          id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL, step_id INTEGER,
          answer TEXT DEFAULT '', file_id TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS access_codes(
          id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, uses_max INTEGER NOT NULL DEFAULT 1,
          uses_count INTEGER NOT NULL DEFAULT 0, expires_at TEXT DEFAULT '', user_id INTEGER DEFAULT NULL,
          service_id INTEGER DEFAULT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins(
          platform TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'manager',
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
          PRIMARY KEY(platform,user_id)
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS buttons(key TEXT PRIMARY KEY, label TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS audit_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, actor_id TEXT, action TEXT NOT NULL,
          target TEXT DEFAULT '', details TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notifications(
          id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, recipient_id TEXT, kind TEXT,
          text TEXT, sent INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_requests_user ON requests(user_id);
        CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
        CREATE INDEX IF NOT EXISTS idx_answers_request ON request_answers(request_id);
        """)
        defaults = {
            "welcome":"سلام و خوش آمدید 🌷\nبه نت‌یار خوش آمدید.",
            "support":"برای پشتیبانی با دفتر تماس بگیرید.",
            "about":"نت‌یار؛ سامانه خدمات کافی‌نت.",
            "announcements":"در حال حاضر اطلاعیه‌ای ثبت نشده است.",
            "maintenance":"ربات موقتاً بسته است. لطفاً بعداً تلاش کنید.",
            "bot_open":"1", "card_number":"", "card_owner":""
        }
        for k,v in defaults.items():
            self.conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
        buttons = {
            "services":"🏢 خدمات", "track":"🔎 پیگیری", "announcements":"📢 اطلاعیه‌ها",
            "support":"☎️ پشتیبانی", "about":"ℹ️ درباره ما", "admin":"🛠 مدیریت"
        }
        for k,v in buttons.items():
            self.conn.execute("INSERT OR IGNORE INTO buttons(key,label) VALUES(?,?)",(k,v))
        self.conn.commit()

    def setting(self,key,default=""):
        r=self.conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self,key,value):
        self.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,str(value)))
        self.conn.commit()

    def button(self,key):
        r=self.conn.execute("SELECT label,enabled FROM buttons WHERE key=?",(key,)).fetchone()
        return (r["label"],bool(r["enabled"])) if r else (key,True)

    def audit(self, platform, actor, action, target="", details=""):
        self.conn.execute("INSERT INTO audit_log(platform,actor_id,action,target,details,created_at) VALUES(?,?,?,?,?,?)",
                          (platform,str(actor),action,str(target),str(details),utcnow()))
        self.conn.commit()

    def user(self, uid, platform="telegram", username="", full_name=""):
        t=utcnow()
        self.conn.execute("""INSERT INTO users(id,platform,username,full_name,created_at,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            platform=excluded.platform,username=excluded.username,full_name=excluded.full_name,updated_at=excluded.updated_at""",
            (int(uid),platform,username or "",full_name or "",t,t))
        self.conn.commit()

    def is_admin(self, platform, uid):
        env = os.getenv("ADMIN_IDS" if platform=="telegram" else "RUBIKA_ADMIN_IDS","")
        if str(uid) in {x.strip() for x in env.replace(";",",").split(",") if x.strip()}:
            return True
        r=self.conn.execute("SELECT 1 FROM admins WHERE platform=? AND user_id=? AND active=1",(platform,str(uid))).fetchone()
        return bool(r)

    def role(self, platform, uid):
        r=self.conn.execute("SELECT role FROM admins WHERE platform=? AND user_id=? AND active=1",(platform,str(uid))).fetchone()
        if r:return r["role"]
        return "owner" if self.is_admin(platform,uid) else "user"

    def can(self, platform, uid, permission):
        role=self.role(platform,uid)
        matrix={
          "owner":{"*"}, "admin":{"*"},
          "manager":{"services","requests","users","reports","broadcast"},
          "operator":{"requests","users"},
          "support":{"users","requests"},
        }
        return permission in matrix.get(role,set()) or "*" in matrix.get(role,set())

    def service(self,sid,active_only=False):
        q="SELECT * FROM services WHERE id=?"+(" AND active=1" if active_only else "")
        return self.conn.execute(q,(sid,)).fetchone()

    def services(self,active_only=True):
        return self.conn.execute("SELECT * FROM services "+("WHERE active=1 " if active_only else "")+"ORDER BY id").fetchall()

    def steps(self,sid):
        return self.conn.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no",(sid,)).fetchall()

    def create_code(self, uses=1, expires_at="", user_id=None, service_id=None):
        for _ in range(10):
            code=secrets.token_hex(4).upper()
            try:
                self.conn.execute("INSERT INTO access_codes(code,uses_max,expires_at,user_id,service_id,created_at) VALUES(?,?,?,?,?,?)",
                                  (code,max(1,int(uses)),expires_at or "",user_id,service_id,utcnow()))
                self.conn.commit(); return code
            except sqlite3.IntegrityError: continue
        raise RuntimeError("Could not generate unique access code")

    def validate_code(self, code, user_id=None, service_id=None):
        r=self.conn.execute("SELECT * FROM access_codes WHERE code=? AND active=1",(code.strip().upper(),)).fetchone()
        if not r:return False,"کد نامعتبر است."
        if r["uses_count"]>=r["uses_max"]:return False,"سقف استفاده از این کد تمام شده است."
        if r["expires_at"] and r["expires_at"] < utcnow():return False,"اعتبار این کد تمام شده است."
        if r["user_id"] and user_id is not None and r["user_id"] != int(user_id):return False,"این کد برای کاربر دیگری است."
        if r["service_id"] and service_id is not None and r["service_id"] != int(service_id):return False,"این کد برای این خدمت نیست."
        return True,r

    def consume_code(self, code):
        self.conn.execute("UPDATE access_codes SET uses_count=uses_count+1 WHERE code=? AND active=1 AND uses_count<uses_max",(code.strip().upper(),))
        self.conn.commit()

db=Database()
