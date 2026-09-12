"""Canonical Telegram UI: inline menus + one persistent restart button."""
from collections import OrderedDict
import threading, logging
from types import SimpleNamespace
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, ApplicationHandlerStop, filters
log=logging.getLogger("netyar.telegram.inline_only")
_ACTIONS=OrderedDict(); _LOCK=threading.Lock(); _SEQ=0; _REMOVED=set(); _RESTART_CHATS=set()
def _remember(label):
    global _SEQ
    with _LOCK:
        _SEQ+=1; key=f"ik:{_SEQ}"; _ACTIONS[key]=str(label)
        while len(_ACTIONS)>3000:_ACTIONS.popitem(last=False)
    return key
def _clean_label(label):
    s=str(label or "").strip()
    for p in ("🟦 ","🟩 ","🟨 ","🔵 "):
        if s.startswith(p):s=s[len(p):].strip()
    return s
def _inline_kb(rows):
    out=[]
    for row in rows or []:
        bs=[]
        for item in row or []:
            label=str(item[1]) if isinstance(item,(tuple,list)) and len(item)>=2 else str(item); label=_clean_label(label)
            if label:bs.append(InlineKeyboardButton(label,callback_data=_remember(label)))
        if bs:out.append(bs)
    return InlineKeyboardMarkup(out)
class _InlineOnlyReplyKeyboard:
    def __new__(cls,keyboard,*args,**kwargs):return _inline_kb(keyboard)
def restart_keyboard():return ReplyKeyboardMarkup([["🔄 شروع مجدد"]],resize_keyboard=True,is_persistent=True)
async def _remove_legacy_keyboard(message):
    if not message:return
    cid=getattr(getattr(message,"chat",None),"id",None)
    if cid is None or cid in _REMOVED or cid in _RESTART_CHATS:return
    try:
        probe=await message.reply_text("\u2063",reply_markup=ReplyKeyboardRemove());_REMOVED.add(cid)
        try:await probe.delete()
        except Exception:pass
    except Exception:pass
async def _remove_on_message(update,context):
    msg=getattr(update,"effective_message",None)
    if getattr(msg,"text",None)=="🔄 شروع مجدد":return
    await _remove_legacy_keyboard(msg)
def _button_label_from_message(q):
    try:
        for row in getattr(getattr(q.message,"reply_markup",None),"inline_keyboard",[]) or []:
            for b in row:
                if getattr(b,"callback_data",None)==str(q.data or ""):return _clean_label(getattr(b,"text","") or "")
    except Exception:log.exception("inline button label recovery failed")
    return ""
def _message_update_from_callback(update,q):return SimpleNamespace(update_id=getattr(update,"update_id",None),message=q.message,effective_message=q.message,effective_user=q.from_user,effective_chat=getattr(q.message,"chat",None),callback_query=q)
async def _inline_callback(update,context,B):
    q=update.callback_query; label=_ACTIONS.get(str(q.data or "")) or _button_label_from_message(q)
    if not label:await q.answer("این گزینه دیگر معتبر نیست؛ لطفاً از منوی فعلی استفاده کنید.");return
    label=_clean_label(label);await q.answer();original=getattr(q.message,"text",None);proxy=_message_update_from_callback(update,q)
    try:object.__setattr__(q.message,"text",label);await B.router(proxy,context)
    except Exception:
        log.exception("Inline button routing failed: %s",label)
        try:await q.message.reply_text("❌ اجرای این گزینه با خطا مواجه شد. لطفاً دوباره همین گزینه را بزنید.")
        except Exception:pass
    finally:
        try:object.__setattr__(q.message,"text",original)
        except Exception:pass
def reassert(B):
    B.kb=_inline_kb;B.ReplyKeyboardMarkup=_InlineOnlyReplyKeyboard;B.restart_keyboard=restart_keyboard
    log.info("Telegram inline keyboard constructors reasserted")
def install(app,B):
    if getattr(B,"_netyar_no_reply_keyboard",False):return
    reassert(B)
    for name in ("telegram_admin_plus","telegram_ux_billing","telegram_button_fix","sitecustomize"):
        try:
            m=__import__(name)
            if hasattr(m,"ReplyKeyboardMarkup"):m.ReplyKeyboardMarkup=_InlineOnlyReplyKeyboard
        except Exception:pass
    old_start=B.start
    async def _restart(update,context):
        await old_start(update,context)
        try:
            cid=getattr(getattr(update,"effective_chat",None),"id",None)
            if cid is not None:_RESTART_CHATS.add(cid)
            await update.effective_message.reply_text("\u2063",reply_markup=restart_keyboard())
        except Exception:log.exception("failed to install restart keyboard")
        raise ApplicationHandlerStop
    app.add_handler(CommandHandler("start",_restart),group=-301)
    app.add_handler(MessageHandler(filters.TEXT&filters.Regex(r"^🔄 شروع مجدد$"),_restart),group=-300)
    app.add_handler(MessageHandler(filters.ALL,_remove_on_message),group=-200)
    app.add_handler(CallbackQueryHandler(lambda u,c:_inline_callback(u,c,B),pattern=r"^ik:"),group=-98)
    B._netyar_no_reply_keyboard=True
