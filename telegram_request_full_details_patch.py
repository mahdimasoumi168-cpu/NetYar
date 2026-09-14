"""Canonical complete Telegram request details/notifications."""
import logging
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,ApplicationHandlerStop
log=logging.getLogger("netyar.request_full_details")
def _lang(B,rid):
 try:
  import request_language_actions as L;return L.request_language(B.db,rid)
 except Exception:return "fa"
def _keyboard(rid,lang="fa",include_view=False):
 try:
  import request_language_actions as L;return L.admin_markup(rid,lang,include_view=include_view)
 except Exception:return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت",callback_data="adm:menu")]])
def _value(v):return "" if v is None else str(v).strip()
def _full_text(B,rid):
 r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(int(rid),)).fetchone()
 if not r:return None,[]
 lang=_lang(B,rid)
 try:
  import request_language_actions as L;labels=L.labels(lang);service=L.service_name(r["service_key"],lang);field_label=L.field_label
 except Exception:
  labels={"details":"📋 اطلاعات کامل درخواست","tracking":"🎫 کد پیگیری","service":"🧾 خدمت","status":"📌 وضعیت","amount":"💰 مبلغ","payment":"💳 وضعیت پرداخت","method":"💵 روش پرداخت","time":"🕐 زمان ثبت","info":"📋 اطلاعات ثبت‌شده"};service=_value(r["service_key"]);field_label=lambda k,l:f"📋 {k}"
 chat=""
 try:chat=B.db.setting(f"request_chat_{rid}","").strip()
 except Exception:pass
 requester=f"{labels.get('requester','👤 درخواست‌دهنده')}: {chat or _value(r['user_id'])}"
 currency={"fa":"تومان","en":"Toman","ar":"تومان"}.get(lang,"تومان")
 lines=[labels["details"],"",f"{labels['tracking']}: {_value(r['tracking_code'])}",f"{labels['service']}: {service}",requester,f"{labels['status']}: {_value(r['status'])}",f"{labels['amount']}: {int(r['amount'] or 0):,} {currency}",f"{labels['payment']}: {_value(r['payment_status'])}"]
 if r["payment_method"]:lines.append(f"{labels['method']}: {_value(r['payment_method'])}")
 if r["created_at"]:lines.append(f"{labels['time']}: {_value(r['created_at'])}")
 for key in r.keys():
  if key in {"id","tracking_code","service_key","status","amount","payment_status","payment_method","created_at","updated_at","language"}:continue
  val=_value(r[key])
  if val:lines.append(f"{field_label(key,lang)}: {val}")
 lines += ["",labels["info"]]
 files=[]
 for row in B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(int(rid),)).fetchall():
  key=_value(row["field_key"]);ans=_value(row["answer"]);fid=_value(row["file_id"])
  if ans:lines.append(f"{field_label(key,lang)}: {ans}")
  if fid:
   if not ans:lines.append(f"{field_label(key,lang)}: 📎")
   files.append((key,fid))
 return "\n".join(lines),files
async def _send_media(bot,aid,files,rid,lang):
 for key,fid in files:
  try:await bot.send_photo(chat_id=int(aid),photo=fid,caption=f"📎 {key} | #{rid}")
  except Exception:
   try:await bot.send_document(chat_id=int(aid),document=fid,caption=f"📎 {key} | #{rid}")
   except Exception:log.exception("request media delivery failed: %s",rid)
async def _bottom(update,context,B,rid):
 text,files=_full_text(B,rid)
 if text is None:await update.callback_query.answer("Request not found",show_alert=True);raise ApplicationHandlerStop
 q=update.callback_query;lang=_lang(B,rid);await q.message.reply_text(text,reply_markup=_keyboard(rid,lang,False));await _send_media(context.bot,q.from_user.id,files,rid,lang);await q.answer("📤 انتقال به آخر چت");raise ApplicationHandlerStop
def install(app,B):
 if getattr(B,"_request_full_details_patch",False):return True
 async def callback(update,context):
  q=update.callback_query
  if not q or not B.admin(q.from_user.id):return
  data=str(q.data or "")
  if data.startswith("req:bottom:"):
   try:rid=int(data.rsplit(":",1)[1])
   except Exception:return
   return await _bottom(update,context,B,rid)
 app.add_handler(CallbackQueryHandler(callback,pattern=r"^req:bottom:\d+$"),group=-110);B._request_full_details_patch=True;return True
def finalize(B):
 if getattr(B,"_request_full_notify_patch",False):return True
 old=getattr(B,"notify_admins",None)
 if old is None:return False
 async def notify_admins(application,message,request_id=None,inline=None,files=None,**kwargs):
  if not request_id:return await old(application,message,request_id,inline)
  try:
   text,stored_files=_full_text(B,int(request_id))
   if not text:return await old(application,message,request_id,inline)
   lang=_lang(B,int(request_id));mk=_keyboard(int(request_id),lang,True);admins=list(dict.fromkeys(getattr(B,"ADM",set()) or []));ok=True
   for aid in admins:
    delivered=False
    for _ in range(3):
     try:await application.bot.send_message(chat_id=int(aid),text=text,reply_markup=mk);delivered=True;break
     except Exception:pass
    if not delivered:ok=False;log.exception("complete request notification failed: %s",request_id)
   all_files=list(stored_files)
   for item in list(files or []):
    if isinstance(item,dict) and item.get("file_id"):all_files.append((item.get("type","photo"),item["file_id"]))
    elif item:all_files.append(("photo",str(item)))
   for aid in admins:
    for item in all_files:
     try:
      fid=item[1] if isinstance(item,tuple) else item;kind=item[0] if isinstance(item,tuple) else "photo"
      if kind=="document":await application.bot.send_document(chat_id=int(aid),document=fid)
      else:await application.bot.send_photo(chat_id=int(aid),photo=fid)
     except Exception:
      try:await application.bot.send_document(chat_id=int(aid),document=fid)
      except Exception:log.exception("request attachment notification failed: %s",request_id)
   return ok
  except Exception:log.exception("complete request notification wrapper failed: %s",request_id);return await old(application,message,request_id,inline)
 B.notify_admins=notify_admins;B._request_full_notify_patch=True;return True
