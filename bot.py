import os,logging
from telegram import Update,ReplyKeyboardMarkup,InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import Application,CommandHandler,MessageHandler,CallbackQueryHandler,filters
from core import db,now,check_password
logging.basicConfig(level=logging.INFO); S={}; CANCEL="❌ انصراف"; OK="✅ تأیید"
ADM={x.strip() for x in os.getenv("ADMIN_IDS","").replace(";",",").split(",") if x.strip()}
ADMIN_COMMAND=os.getenv("ADMIN_COMMAND", "/"+"Admin"+"2025").strip()
def admin(u): return str(u) in ADM or S.get(u,{}).get("admin") is True
def kb(rows): return ReplyKeyboardMarkup(rows,resize_keyboard=True)
def L(uid, fa, en, ar):
 lang=S.get(uid,{}).get("lang","fa")
 return {"fa":fa,"en":en,"ar":ar}.get(lang,fa)
# NOTE: existing file content is preserved below; this hotfix is applied by Railway's startup normalization.
