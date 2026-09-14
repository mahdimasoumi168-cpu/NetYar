"""Service notifications with complete request data and stable admin actions."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters
log=logging.getLogger("netyar.telegram.notifications"); B=None

def _lang(rid):
 try:
  import request_language_actions as L
  return L.request_language(B.db,rid)
 except Exception:return "fa"

def _admin_markup(rid):
 try:
  import request_language_actions as L
  return L.admin_markup(rid,_lang(rid))
 except Exception:
  return InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده اطلاعات کامل",callback_data=f"panel:req:{rid}")],[InlineKeyboardButton("⏳ در حال بررسی",callback_data=f"panel:review:{rid}"),InlineKeyboardButton("✅ انجام شد",callback_data=f"panel:approve:{rid}")],[InlineKeyboardButton("❌ رد درخواست",callback_data=f"panel:reject:{rid}"),InlineKeyboardButton("✉️ پاسخ به مشترک",callback_data=f"req:r:{rid}")],[InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت",callback_data="adm:menu")]])

def _label(key,lang):
 try:
  import request_language_actions as L
  return L.field_label(key,lang)
 except Exception:return f"📋 {key}"

def _service(key,lang):
 try:
  import request_language_actions as L
  return L.service_name(key,lang)
 except Exception:return str(key or "-")

def _full_request(rid):
 r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
 if not r:return ""
 lang=_lang(rid)
 lines=[f"🎫 کد پیگیری: {r['tracking_code']}",f"🧾 خدمت: {_service(r['service_key'],lang)}",f"📌 وضعیت: {r['status'] or '-'}",f"💰 مبلغ: {int(r['amount'] or 0):,} تومان",f"💳 وضعیت پرداخت: {r['payment_status'] or '-'}"]
 if r['payment_method']:lines.append(f"💵 روش پرداخت: {r['payment_method']}")
 for k in r.keys():
  if k in {'id','tracking_code','service_key','status','amount','payment_status','payment_method','created_at','updated_at','language','user_id'}:continue
  v=str(r[k] or '').strip()
  if v:lines.append(f"{_label(k,lang)}: {v}")
 answers=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
 lines.append("\n📋 همه گزینه‌ها و اطلاعات واردشده:")
 for a in answers:
  v=str(a['answer'] or '').strip();f=a['file_id']
  if v:lines.append(f"{_label(a['field_key'],lang)}: {v}")
  if f:lines.append(f"📎 پیوست مربوط به {_label(a['field_key'],lang)} ارسال شده است.")
 return "\n".join(lines)

def _localize(text,rid):
 try:
  import telegram_notification_guard as N
  return N._localize_text(text,_lang(rid)) if rid else text
 except Exception:return text

def _partner_keyboard():
 return B.kb([['➕ شارژ حساب','🏛 حل مشکل سامانه دولت من'],['🎫 درخواست‌های من','🔎 پیگیری کد'],['📋 سوابق','💰 موجودی'],['📨 ارسال پیام به مدیریت'],['🚪 خروج از پنل'],[B.CANCEL]])

async def _send_to_admins(bot,text,photo_id=None,document_id=None,rid=None):
 if not B.ADM:return
 markup=_admin_markup(rid) if rid else None
 text=_localize(text,rid)
 for aid in B.ADM:
  try:
   if photo_id: await bot.send_photo(chat_id=int(aid),photo=photo_id,caption=text,reply_markup=markup)
   elif document_id: await bot.send_document(chat_id=int(aid),document=document_id,caption=text,reply_markup=markup)
   else: await bot.send_message(chat_id=int(aid),text=text,reply_markup=markup)
  except Exception:log.exception("admin notification failed")

async def _media(update,context):
 uid=update.effective_user.id; st=B.S.setdefault(uid,{}); mode=st.get('mode')
 if mode not in {'gov_photo','fida_doc','print'}:return
 snapshot=dict(st); owner=st.get('partner_id') or B.db.user('telegram',uid,update.effective_user.username,update.effective_user.full_name)
 before=B.db.conn.execute('SELECT id FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1',(owner,)).fetchone()
 await B.media(update,context)
 after=B.db.conn.execute('SELECT id,tracking_code,service_key,status FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 1',(owner,)).fetchone()
 photo_id=update.message.photo[-1].file_id if update.message.photo else None; document_id=update.message.document.file_id if update.message.document else None
 if mode=='gov_photo' and after and (not before or after['id']!=before['id']):
  rid=after['id']; full=_full_request(rid)
  text=f'👔 مدیر — اعلان خدمات جدید\n\n🆕 درخواست حل مشکل سامانه دولت من\n\n{full}\n\n📎 پیوست همین درخواست نیز ارسال شده است.'
  await _send_to_admins(context.bot,text,photo_id,document_id,rid)
 elif mode=='fida_doc': await _send_to_admins(context.bot,f'👔 مدیر — اعلان خدمات جدید\n\n📄 مدرک فیدا از مشترک دریافت شد.\n👤 شناسه کاربر: {uid}\n📎 مدرک پیوست شده است.',photo_id,document_id)
 elif mode=='print': await _send_to_admins(context.bot,f'👔 مدیر — اعلان خدمات جدید\n\n🖨 فایل جدید برای خدمات چاپ دریافت شد.\n👤 شناسه کاربر: {uid}\n📎 فایل پیوست شده است.',photo_id,document_id)
 raise ApplicationHandlerStop

def install(app,bot_module):
 global B;B=bot_module
 B.partner_kb=lambda lang='fa':_partner_keyboard()
 app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,_media),group=-2)
