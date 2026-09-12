"""Canonical Telegram UI and callback routing.

Only one ReplyKeyboard button is kept below the chat: ``🔄 شروع مجدد``.
All normal options are inline buttons attached to messages.
"""
from contextvars import ContextVar
from types import SimpleNamespace
import secrets
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, TypeHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.ui")
RESTART = "🔄 شروع مجدد"
CANCEL = "❌ انصراف"
_CURRENT_UID = ContextVar("netyar_ui_uid", default=None)


def _init_db(B):
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS ui2_callbacks(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,label TEXT NOT NULL,lang TEXT,status TEXT,created_at TEXT NOT NULL)")
    for col in ("lang", "status"):
        try:B.db.conn.execute(f"ALTER TABLE ui2_callbacks ADD COLUMN {col} TEXT")
        except Exception:pass
    B.db.conn.commit()


def _uid():return _CURRENT_UID.get()


def _token(B,uid,label):
    token=secrets.token_urlsafe(24);st=B.S.get(uid,{}) if uid is not None else {}
    B.db.conn.execute("INSERT INTO ui2_callbacks(token,user_id,label,lang,status,created_at) VALUES(?,?,?,?,?,?)",(token,str(uid or ""),str(label),st.get("lang"),st.get("status"),B.now()))
    B.db.conn.commit();return token


def inline(rows,B,uid=None):
    uid=uid if uid is not None else _uid();out=[]
    for row in rows or []:
        buttons=[]
        for item in row or []:
            label=str(item[0] if isinstance(item,(tuple,list)) else item)
            buttons.append(InlineKeyboardButton(label,callback_data="ui2:"+_token(B,uid,label)))
        if buttons:out.append(buttons)
    return InlineKeyboardMarkup(out)


def restart_keyboard():
    return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,one_time_keyboard=False,is_persistent=True)


def _main_rows(B,uid):
    st=B.S.get(uid,{})
    if st.get("status")=="iranian":
        rows=[["🎫 پیگیری","💰 کیف پول من"],["📞 تماس با ما","📝 ثبت شکایت مشتریان"]]
    else:
        rows=[["🪪 فیدای غیر حضوری","🖨 خدمات چاپ"],["🪪 حل مشکل ورود اتباع دولت من","🎫 کد رهگیری تمدید کارت‌ها"],["📱 خدمات سیم کارت","📝 آزمون غربالگری"],["🎫 پیگیری","💰 کیف پول من"],["📞 تماس با ما","📝 ثبت شکایت مشتریان"]]
    # Partner panel is shown only to an actually authorized partner/admin.
    partner_ok=bool(st.get("partner_id") and st.get("partner_active",True)) or bool(B.admin(uid))
    if not partner_ok:
        try:
            phone=str(st.get("phone") or "").strip()
            if phone:
                row=B.db.conn.execute("SELECT id FROM partners WHERE phone=? AND active=1",(phone,)).fetchone()
                partner_ok=bool(row)
                if partner_ok:
                    st["partner_id"]=row["id"]
                    st["partner_active"]=1
        except Exception:
            log.exception("partner resolution failed")
    if partner_ok:rows.append(["👥 پنل همکاران"])
    if B.admin(uid):rows.append(["🛠 پنل مدیریت بات"])
    return rows


def _fake(update,label):
    q=update.callback_query
    class MessageProxy:
        __slots__=("_message","text")
        def __init__(self,message,text):self._message,self.text=message,text
        def __getattr__(self,name):return getattr(self._message,name)
    msg=MessageProxy(q.message,label)
    return SimpleNamespace(update_id=update.update_id,message=msg,effective_message=msg,effective_user=q.from_user,effective_chat=q.message.chat,callback_query=q)


async def _wallet(update,context,B):
    uid=update.effective_user.id;fn=getattr(B,"customer_wallet",None)
    if fn:return await fn(update,context)
    return await update.effective_message.reply_text("💰 کیف پول من\n\nموجودی کیف پول شما فعلاً صفر است.",reply_markup=B.main(uid))


async def _complaint_text(update,context,B):
    if not update.message:return
    uid=update.effective_user.id;st=B.S.setdefault(uid,{})
    if st.get("mode")!="ui2_complaint":return
    text=(update.message.text or "").strip()
    if not text:return await update.message.reply_text("❌ متن شکایت خالی است.",reply_markup=B.cancel_kb(st.get("lang","fa")))
    user=update.effective_user;username=f"@{user.username}" if user.username else "ندارد"
    message=("📝 شکایت/انتقاد جدید\n\n" f"👤 نام: {user.full_name or '-'}\n" f"🔹 آیدی: {user.id}\n" f"🔹 یوزرنیم: {username}\n\n" f"💬 متن:\n{text}")
    try:await B.notify_admins(context.application,message)
    except Exception:log.exception("complaint notification failed")
    st["mode"]=None
    await update.message.reply_text("✅ شکایت شما برای مدیریت ارسال شد.",reply_markup=B.main(uid))
    raise ApplicationHandlerStop


async def _dispatch(update,context,B,label):
    q=update.callback_query;uid=q.from_user.id;st=B.S.setdefault(uid,{});fake=_fake(update,label)
    if label==RESTART:return await B.start(fake,context)
    if label==CANCEL:return await B.cancel(fake,context)
    if label=="👥 پنل همکاران":return await B.partner(fake,context)
    if label=="🚪 خروج از پنل":return await B.partner_exit(fake,context)
    if label=="🛠 پنل مدیریت بات":
        if not B.admin(uid):return await q.message.reply_text("❌ دسترسی مدیریت ندارید.",reply_markup=B.main(uid))
        import telegram_admin_plus as A
        return await A._callback(SimpleNamespace(callback_query=SimpleNamespace(data="adm:menu",from_user=q.from_user,message=q.message),effective_user=q.from_user),context,B)
    if label=="➕ شارژ حساب":
        fn=getattr(B,"topup",None)
        if fn:return await fn(fake,context)
        st["mode"]="topup_amount";return await q.message.reply_text("💰 مبلغ شارژ را به تومان وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
    if label=="🏛 حل مشکل سامانه دولت من":return await B.gov(fake,context)
    if label=="🔎 پیگیری کد":return await B.ptrack(fake,context)
    if label=="📋 سوابق":return await B.phistory(fake,context)
    if label=="💰 موجودی":
        if st.get("partner_id"):
            row=B.db.conn.execute("SELECT balance FROM partners WHERE id=?",(st["partner_id"],)).fetchone();balance=int(row["balance"] or 0) if row else 0
            return await q.message.reply_text(f"💰 اعتبار فعلی شما: {balance:,} تومان",reply_markup=B.partner_kb(st.get("lang","fa")))
        return await _wallet(fake,context,B)
    if label=="🎫 تیکت به مدیریت":
        from telegram_business_features import _send_ticket_prompt
        return await _send_ticket_prompt(fake,B)
    if label=="🪪 فیدای غیر حضوری":return await B.fida(fake,context)
    if label=="🖨 خدمات چاپ":return await B.prt(fake,context)
    if label=="🪪 حل مشکل ورود اتباع دولت من":return await B.gov(fake,context)
    if label=="📱 خدمات سیم کارت":
        fn=getattr(B,"sim_start",None)
        if fn:return await fn(fake,context)
    if label=="🎫 پیگیری":
        st["mode"]="public_tracking"
        return await q.message.reply_text("🎫 کد پیگیری را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
    if label=="💰 کیف پول من":return await _wallet(fake,context,B)
    if label=="📞 تماس با ما":
        return await q.message.reply_text("📞 تماس با ما\n\nبرای ارتباط با پشتیبانی روی دکمه زیر بزنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 ارتباط با پشتیبانی",url="https://t.me/Good_ok_2000")]]))
    if label=="📝 ثبت شکایت مشتریان":
        st["mode"]="ui2_complaint";return await q.message.reply_text("📝 ثبت شکایت مشتریان\n\nمتن شکایت یا انتقاد خود را ارسال کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
    result=await B.router(fake,context)
    if result is not None:return result
    return await q.message.reply_text("❌ این گزینه در حال حاضر در دسترس نیست.",reply_markup=B.main(uid))


def install(app,B):
    if getattr(B,"_inline_ui_v2",False):return
    _init_db(B)
    async def bind(update,context):
        try:_CURRENT_UID.set(getattr(update.effective_user,"id",None))
        except Exception:_CURRENT_UID.set(None)
    app.add_handler(TypeHandler(object,bind),group=-9999)
    B.kb=lambda rows:inline(rows,B)
    B.restart_keyboard=restart_keyboard
    B.main=lambda uid:inline(_main_rows(B,uid),B,uid)
    B.cancel_kb=lambda lang="fa":inline([[CANCEL]],B)
    def admin_menu():
        try:
            import telegram_admin_plus as A;return A._admin_menu()
        except Exception:return inline([["⬅️ منوی اصلی"]],B)
    B.amenu=admin_menu
    try:
        import telegram_business_features as F
        F._partner_kb=lambda: inline([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],["🔎 پیگیری کد","📋 سوابق"],["💰 موجودی","🎫 تیکت به مدیریت"],["🚪 خروج از پنل"],[CANCEL]],B)
        B.partner_kb=lambda lang="fa":F._partner_kb()
    except Exception:pass
    old_start=B.start
    async def start(update,context):
        result=await old_start(update,context)
        try:await update.message.reply_text("دسترسی سریع:",reply_markup=restart_keyboard())
        except Exception:
            try:await update.effective_message.reply_text("دسترسی سریع:",reply_markup=restart_keyboard())
            except Exception:pass
        return result
    B.start=start
    async def callback(update,context):
        q=update.callback_query
        if not q or not str(q.data or "").startswith("ui2:"):return
        token=str(q.data)[4:]
        row=B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=?",(token,)).fetchone()
        if not row:
            await q.answer("این گزینه منقضی شده است.",show_alert=True);return await q.message.reply_text("🔄 لطفاً «شروع مجدد» را بزنید.",reply_markup=restart_keyboard())
        if row["user_id"] and str(row["user_id"])!=str(q.from_user.id):await q.answer("این گزینه برای کاربر دیگری است.",show_alert=True);return
        await q.answer();st=B.S.setdefault(q.from_user.id,{})
        if row["lang"]:st["lang"]=row["lang"]
        if row["status"]:st["status"]=row["status"]
        try:return await _dispatch(update,context,B,str(row["label"]))
        except Exception:
            log.exception("ui2 callback failed label=%r",row["label"])
            return await q.message.reply_text("❌ اجرای گزینه با خطا مواجه شد.\nلطفاً «🔄 شروع مجدد» را بزنید.",reply_markup=restart_keyboard())
    app.add_handler(CallbackQueryHandler(callback,pattern=r"^ui2:"),group=-10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,lambda u,c:_complaint_text(u,c,B)),group=-9)
    B._inline_ui_v2=True
