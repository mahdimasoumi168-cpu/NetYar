"""Stable Telegram UI policy.

Ordinary options are inline buttons attached to the message. The only
ReplyKeyboard kept below the chat is the persistent restart button.
Callback tokens and the user's menu state are persisted in SQLite so visible
buttons survive Railway restarts and do not depend on process-global state.
"""
from types import SimpleNamespace
from contextvars import ContextVar
import secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop, TypeHandler

RESTART="🔄 شروع مجدد"
_CURRENT_UID=ContextVar("netyar_ui_uid",default=None)


def _init_db(B):
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS ui2_callbacks(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,label TEXT NOT NULL,lang TEXT,status TEXT,created_at TEXT NOT NULL)")
    for col,typ in (("lang","TEXT"),("status","TEXT")):
        try:B.db.conn.execute(f"ALTER TABLE ui2_callbacks ADD COLUMN {col} {typ}")
        except Exception:pass
    B.db.conn.commit()


def _uid(): return _CURRENT_UID.get()


def _token(B,uid,label):
    token=secrets.token_urlsafe(24)
    st=B.S.get(uid,{}) if uid is not None else {}
    B.db.conn.execute("INSERT INTO ui2_callbacks(token,user_id,label,lang,status,created_at) VALUES(?,?,?,?,?,?)",(token,str(uid or ""),str(label),st.get("lang"),st.get("status"),B.now()))
    B.db.conn.commit()
    return token


def inline(rows,B=None,uid=None):
    uid=uid if uid is not None else _uid();out=[]
    for row in rows or []:
        buttons=[]
        for item in row or []:
            label=str(item[0] if isinstance(item,(tuple,list)) else item)
            token=_token(B,uid,label) if B is not None else label[:20]
            buttons.append(InlineKeyboardButton(label,callback_data="ui2:"+token))
        if buttons:out.append(buttons)
    return InlineKeyboardMarkup(out)


def restart_keyboard():
    return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)


def _proxy(update,label):
    q=update.callback_query
    class Msg:
        def __init__(self,src,text):self._src,self.text=src,text
        def __getattr__(self,n):return getattr(self._src,n)
    msg=Msg(q.message,label)
    return SimpleNamespace(update_id=update.update_id,message=msg,effective_message=msg,effective_user=q.from_user,effective_chat=q.message.chat,callback_query=q)


def _iranian_main(B,uid):
    return [["🎫 پیگیری","👥 پنل همکاران"],["💰 کیف پول من","📞 تماس با ما"],["📝 ثبت شکایت مشتریان"]]


def _foreign_main(B,uid):
    rows=[["🪪 فیدای غیر حضوری","🖨 خدمات چاپ"],["🪪 حل مشکل ورود اتباع دولت من","🎫 کد رهگیری تمدید کارت‌ها"],["📱 خدمات سیم کارت","📝 آزمون غربالگری"],["🎫 پیگیری","💰 کیف پول من"],["📞 تماس با ما","📝 ثبت شکایت مشتریان"],["👥 پنل همکاران"]]
    if B.admin(uid):rows.append(["🛠 پنل مدیریت بات"])
    return rows


def install(app,B):
    if getattr(B,"_inline_ui_v2",False):return
    _init_db(B)
    async def bind(update,context):
        uid=getattr(update.effective_user,"id",None)
        _CURRENT_UID.set(uid)
    app.add_handler(TypeHandler(object,bind),group=-9999)
    B.kb=lambda rows:inline(rows,B)
    B.restart_keyboard=restart_keyboard
    def main(uid):
        status=B.S.get(uid,{}).get("status");return inline(_iranian_main(B,uid) if status=="iranian" else _foreign_main(B,uid),B,uid)
    B.main=main
    B.cancel_kb=lambda lang="fa":inline([["❌ انصراف"]],B)
    try:
        import telegram_business_features as F
        F._partner_kb=lambda: inline([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🔎 پیگیری کد","📋 سوابق"],["💰 موجودی","🎫 تیکت به مدیریت"],["🚪 خروج از پنل"],["❌ انصراف"]],B)
    except Exception:pass
    old_start=B.start
    async def start(update,context):
        result=await old_start(update,context)
        try:await update.message.reply_text("دسترسی سریع:",reply_markup=restart_keyboard())
        except Exception:pass
        return result
    B.start=start
    async def cb(update,context):
        q=update.callback_query
        if not q or not str(q.data or "").startswith("ui2:"):return
        await q.answer();token=str(q.data)[4:]
        row=B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=?",(token,)).fetchone()
        if not row or (row["user_id"] and str(row["user_id"])!=str(q.from_user.id)):
            return await q.message.reply_text("🔄 این گزینه قدیمی شده است. لطفاً «🔄 شروع مجدد» را بزنید.",reply_markup=restart_keyboard())
        uid=q.from_user.id;st=B.S.setdefault(uid,{})
        if row["lang"]:st["lang"]=row["lang"]
        if row["status"]:st["status"]=row["status"]
        label=str(row["label"]);proxy=_proxy(update,label)
        if label==RESTART:return await B.start(proxy,context)
        if label=="👥 پنل همکاران":return await B.partner(proxy,context)
        if label=="❌ انصراف":return await B.cancel(proxy,context)
        if label in {"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات","پنل مدیریت"} and B.admin(uid):
            import telegram_admin_plus as A
            return await A._callback(SimpleNamespace(callback_query=SimpleNamespace(data="adm:menu",from_user=q.from_user,message=q.message),effective_user=q.from_user),context,B)
        result=await B.router(proxy,context)
        if result is not None:raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(cb,pattern=r"^ui2:"),group=-10)
    B._inline_ui_v2=True
