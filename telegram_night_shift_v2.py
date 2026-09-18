"""Legacy night-shift compatibility module. Access is always allowed 24/7."""
from telegram import ReplyKeyboardMarkup,InlineKeyboardMarkup,InlineKeyboardButton
PREFIX="night_worker:"; RESTART="🔄 شروع مجدد"; PARTNER="👥 پنل همکاران"
def is_friday(): return False
def open_now(): return True
def worker(B,pid): return False
def worker_phone(B,v): return False
def assigned(B,uid): return False
def allowed(B,uid,update=None): return True
def closed(): return "❌ این پیام قدیمی است؛ ربات به‌صورت ۲۴ ساعته فعال است."
def markup(B,uid=None): return ReplyKeyboardMarkup([[RESTART]],resize_keyboard=True,is_persistent=True)
def install(app,B):
    B._night_shift_v2=True
