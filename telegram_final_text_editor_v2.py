"""Final text/button override layer for Telegram admin editing.

Keeps callback_data unchanged while replacing only visible text. This means an
administrator can rename a button without breaking its action.
"""
from __future__ import annotations
import hashlib
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

PREFIX = "ui_replace_"
ORIGINAL = "ui_original_"
STATE = "final_text_editor"


def hid(s):
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:12]


def get(B, key, default=""):
    try: return B.db.setting(key, default) or default
    except Exception: return default


def save(B, key, value):
    B.db.set_setting(key, value)


def replace(B, text):
    s = str(text or "")
    return get(B, PREFIX + hid(s), "") or s


def markup_replace(B, markup):
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    rows=[]
    for row in markup.inline_keyboard:
        nr=[]
        for b in row:
            text = replace(B, getattr(b, "text", ""))
            nr.append(InlineKeyboardButton(text, callback_data=getattr(b, "callback_data", None), url=getattr(b, "url", None), web_app=getattr(b, "web_app", None), login_url=getattr(b, "login_url", None), switch_inline_query=getattr(b, "switch_inline_query", None), switch_inline_query_current_chat=getattr(b, "switch_inline_query_current_chat", None), callback_game=getattr(b, "callback_game", None), pay=getattr(b, "pay", None)))
            original = str(getattr(b, "text", "") or "")
            if original: save(B, ORIGINAL + hid(original), original)
        rows.append(nr)
    return InlineKeyboardMarkup(rows)


def catalog(B):
    try:
        import admin_editable_texts as E
        return E._catalog(B)
    except Exception:
        return []


def page(B, n=0):
    items=catalog(B); size=8; pages=max(1,(len(items)+size-1)//size); n=max(0,min(int(n),pages-1)); rows=[]
    for text in items[n*size:(n+1)*size]:
        save(B, ORIGINAL+hid(text), text)
        rows.append([(replace(B,text)[:42],f"adm:ft:{hid(text)}")])
    nav=[]
    if n: nav.append(("⬅️ قبلی",f"adm:ftpage:{n-1}"))
    if n+1<pages: nav.append(("بعدی ➡️",f"adm:ftpage:{n+1}"))
    if nav: rows.append(nav)
    rows.append([(f"🔎 {len(items)} متن/عنوان قابل ویرایش","adm:ftnoop")])
    rows.append([("⬅️ پنل مدیریت","adm:menu")])
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([[InlineKeyboardButton(str(t),callback_data=d) for t,d in row] for row in rows])


async def install(app,B):
    if not getattr(app,"_final_text_editor_v2",False):
        bot=app.bot
        old_send=bot.send_message
        old_edit=bot.edit_message_text
        async def send(*args,**kwargs):
            if "text" in kwargs: kwargs["text"]=replace(B,kwargs["text"])
            if "reply_markup" in kwargs: kwargs["reply_markup"]=markup_replace(B,kwargs["reply_markup"])
            return await old_send(*args,**kwargs)
        async def edit(*args,**kwargs):
            if "text" in kwargs: kwargs["text"]=replace(B,kwargs["text"])
            if "reply_markup" in kwargs: kwargs["reply_markup"]=markup_replace(B,kwargs["reply_markup"])
            return await old_edit(*args,**kwargs)
        bot.send_message=send; bot.edit_message_text=edit; app._final_text_editor_v2=True

    async def cb(update,context):
        q=update.callback_query
        if not q or not B.admin(q.from_user.id): return
        data=str(q.data or "")
        if data=="adm:ftnoop": await q.answer(); return
        if data=="adm:ui_texts":
            await q.answer(); return await q.message.reply_text("📝 ویرایش کامل متن‌ها و عنوان دکمه‌ها\n\nهر عنوانی را انتخاب کنید؛ عملکرد دکمه و callback آن حفظ می‌شود.\n\nمتن جدید را ارسال کنید:",reply_markup=page(B,0))
        if data.startswith("adm:ftpage:"):
            await q.answer(); return await q.message.reply_text("📝 ویرایش کامل متن‌ها و عنوان دکمه‌ها",reply_markup=page(B,int(data.rsplit(":",1)[1])))
        if data.startswith("adm:ft:"):
            await q.answer(); h=data.split(":",2)[2]; original=get(B,ORIGINAL+h,"")
            if not original: return await q.message.reply_text("❌ این متن پیدا نشد. فهرست را دوباره باز کنید.")
            st=B.S.setdefault(q.from_user.id,{})
            st[STATE]={"hash":h,"original":original}
            current=replace(B,original)
            return await q.message.reply_text(f"✏️ ویرایش متن/عنوان\n\nفعلی:\n{current}\n\nمتن جدید را کامل ارسال کنید:")

    async def text(update,context):
        if not update.message or not B.admin(update.effective_user.id): return
        st=B.S.setdefault(update.effective_user.id,{})
        data=st.get(STATE)
        if not data:return
        value=(update.message.text or "").strip()
        if not value:return await update.message.reply_text("❌ متن خالی قابل ذخیره نیست.")
        save(B,PREFIX+data["hash"],value)
        st.pop(STATE,None)
        return await update.message.reply_text("✅ متن/عنوان ذخیره شد. عملکرد دکمه تغییر نکرد.",reply_markup=page(B,0))

    app.add_handler(CallbackQueryHandler(cb,pattern=r"^adm:(ui_texts|ftpage:|ft:|ftnoop)$"),group=-21000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-20999)
    return True
