"""After-hours partner whitelist controlled from the admin panel."""
import re
import telegram_final_control as F
from telegram.ext import MessageHandler, filters

KEY_PREFIX = "after_hours_phone:"
MENU = "🌙 همکاران شیفت شب"

def _phone(v):
    s=str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s=re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"): s="0"+s[3:]
    if s.startswith("0098"): s="0"+s[4:]
    return s if re.fullmatch(r"09\d{9}",s) else None

def _allowed(B, phone):
    p=_phone(phone)
    if not p: return False
    try: return B.db.setting(KEY_PREFIX+p,"") == "1"
    except Exception: return False

def install(app,B):
    if getattr(app,"_night_shift_access",False): return
    old_perm=F._permanent_partner
    def perm(B,uid):
        st=B.S.get(uid,{}) or {}
        return old_perm(B,uid) or _allowed(B,st.get("phone"))
    F._permanent_partner=perm
    old_menu=getattr(B,"amenu",None)
    if old_menu:
        def amenu():
            kb=old_menu()
            try: kb.keyboard.append([__import__('telegram').KeyboardButton(MENU)])
            except Exception: pass
            return kb
        B.amenu=amenu
    async def admin_handler(update,context):
        uid=update.effective_user.id
        if not B.admin(uid) or not update.message: return
        st=B.S.setdefault(uid,{})
        t=(update.message.text or "").strip(); mode=st.get("mode")
        if t==MENU:
            B.db.conn.execute("CREATE TABLE IF NOT EXISTS night_shift_partners(phone TEXT PRIMARY KEY,active INTEGER NOT NULL DEFAULT 1,created_at TEXT)")
            B.db.conn.commit()
            rs=B.db.conn.execute("SELECT phone,active FROM night_shift_partners ORDER BY phone").fetchall()
            txt="🌙 همکاران شیفت شب\n\n"+("\n".join(f"{'🟢' if r['active'] else '🔴'} {r['phone']}" for r in rs) or "هنوز شماره‌ای تعریف نشده است.")
            return await update.message.reply_text(txt,reply_markup=B.kb([["➕ افزودن همکار شیفت شب"],["➖ حذف همکار شیفت شب"],["⬅️ منوی اصلی"]]))
        if t=="➕ افزودن همکار شیفت شب":
            st["mode"]="night_add"; return await update.message.reply_text("📱 شماره موبایل همکار شیفت شب را وارد کنید:")
        if t=="➖ حذف همکار شیفت شب":
            st["mode"]="night_del"; return await update.message.reply_text("📱 شماره موبایل همکار را برای حذف دسترسی شب وارد کنید:")
        if mode in {"night_add","night_del"}:
            p=_phone(t)
            if not p: return await update.message.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789")
            B.db.conn.execute("CREATE TABLE IF NOT EXISTS night_shift_partners(phone TEXT PRIMARY KEY,active INTEGER NOT NULL DEFAULT 1,created_at TEXT)")
            if mode=="night_add":
                B.db.conn.execute("INSERT OR REPLACE INTO night_shift_partners(phone,active,created_at) VALUES(?,?,datetime('now'))",(p,1)); B.db.set_setting(KEY_PREFIX+p,"1")
                msg="✅ شماره ثبت شد؛ این همکار خارج از ساعت کاری هم اجازه ورود به پنل همکاران را دارد."
            else:
                B.db.conn.execute("UPDATE night_shift_partners SET active=0 WHERE phone=?",(p,)); B.db.set_setting(KEY_PREFIX+p,"0")
                msg="✅ دسترسی شب این شماره حذف شد."
            B.db.conn.commit(); st["mode"]="v5"
            return await update.message.reply_text(msg,reply_markup=B.amenu())
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,admin_handler),group=-5002)
    app._night_shift_access=True
